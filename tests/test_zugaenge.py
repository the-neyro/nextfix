"""Alle drei Zugänge (UI, REST, MCP) arbeiten auf denselben Daten."""

import asyncio

from fastapi.testclient import TestClient

from app.mcp_server import server
from app.web import app

client = TestClient(app)


def test_api_anlegen_und_liste():
    r = client.post("/api/projekte", json={"domain": "example.de", "name": "Test"})
    assert r.status_code == 201
    assert client.get("/api/projekte").json()[0]["name"] == "Test"


def test_api_fehler():
    assert client.post("/api/projekte", json={"domain": "kaputt"}).status_code == 400
    assert client.delete("/api/projekte/999").status_code == 404


def test_ui_zeigt_projekt_aus_api():
    client.post("/api/projekte", json={"domain": "example.de"})
    r = client.get("/")
    assert r.status_code == 200
    assert "example.de" in r.text


def test_ui_formular():
    r = client.post("/projekte", data={"domain": "https://shop.example.de", "name": ""})
    assert "shop.example.de" in r.text


def test_mcp_sieht_dasselbe_wie_api():
    client.post("/api/projekte", json={"domain": "example.de"})
    tools = {t.name for t in asyncio.run(server.list_tools())}
    assert {"projekte_liste", "projekt_anlegen", "projekt_loeschen"} <= tools

    asyncio.run(server.call_tool("projekt_anlegen", {"domain": "zweite.de"}))
    domains = [p["domain"] for p in client.get("/api/projekte").json()]
    assert domains == ["example.de", "zweite.de"]


def test_audit_ueber_api_ui_und_mcp(testseite):
    """Ein Crawl, der per API gestartet wird, ist in UI und MCP sichtbar."""
    pid = client.post("/api/projekte", json={"domain": "127.0.0.1"}).json()["id"]
    r = client.put(f"/api/projekte/{pid}/einstellungen", json={"start_url": testseite, "crawl_delay": 0})
    assert r.json()["start_url"] == testseite
    assert client.put(f"/api/projekte/{pid}/einstellungen", json={"seitenlimit": -1}).status_code == 400

    crawl = client.post(f"/api/projekte/{pid}/crawls?warten=true").json()
    cid = crawl["id"]
    assert crawl["status"] == "fertig"
    assert client.get(f"/api/crawls/{cid}/uebersicht").json()["seiten"]["gesamt"] == 11
    issues = client.get(f"/api/crawls/{cid}/issues?schwere=error").json()
    assert issues and all(i["schwere"] == "error" for i in issues)
    assert client.get(f"/api/crawls/{cid}/issues/status_4xx").json()["treffer"][0]["url"].endswith("/kaputt")
    assert client.get(f"/api/crawls/{cid}/issues/gibtsnicht").status_code == 400
    assert len(client.get(f"/api/crawls/{cid}/seiten?nur_mit_problemen=true").json()) > 0
    assert client.get(f"/api/crawls/{cid}/seite", params={"url": testseite + "gut"}).status_code == 200
    assert client.get("/api/crawls/9999").status_code == 404
    assert len(client.get("/api/checks").json()) > 40

    # Web-UI rendert alle Seiten
    start = client.get(f"/projekte/{pid}").text
    assert "Website-Zustand" in start and "Was jetzt tun" in start and "Wirkung " in start and "Punkte</span>" not in start
    assert "Sichtbarkeit Google" in start and "Search Console nicht verbunden" in start
    assert "Title-Tag fehlt" in client.get(f"/crawls/{cid}/issues").text
    detail = client.get(f"/crawls/{cid}/issues/status_4xx/seite").text
    assert "So behebst du es" in detail and "/kaputt" in detail
    assert "Einstellungen speichern" in client.get(f"/projekte/{pid}/einstellungen").text
    assert "/kaputt" in client.get(f"/crawls/{cid}/issues/status_4xx").text
    assert "/gut" in client.get(f"/crawls/{cid}/seiten?suche=gut").text
    assert "Gemessene Daten" in client.get(f"/crawls/{cid}/seite", params={"url": testseite + "gut"}).text
    assert client.get("/projekte/9999").status_code == 404

    # MCP: letzter Crawl über projekt_id
    ue = asyncio.run(server.call_tool("uebersicht", {"projekt_id": pid}))
    assert "Health" in str(ue) or "health" in str(ue)
    tools = {t.name for t in asyncio.run(server.list_tools())}
    assert {"crawl_starten", "crawl_status", "issues_liste", "issue_details", "seiten_liste",
            "seite_details", "einstellungen_setzen", "checks_katalog"} <= tools


def test_mcp_crawl_starten(testseite):
    pid = client.post("/api/projekte", json={"domain": "127.0.0.1"}).json()["id"]
    asyncio.run(server.call_tool("einstellungen_setzen", {"projekt_id": pid, "start_url": testseite, "crawl_delay": 0}))
    asyncio.run(server.call_tool("crawl_starten", {"projekt_id": pid}))
    crawls = client.get(f"/api/projekte/{pid}/crawls").json()
    assert crawls[0]["status"] == "fertig"


def test_ui_crawl_starten_im_hintergrund(testseite):
    import time
    pid = client.post("/api/projekte", json={"domain": "127.0.0.1"}).json()["id"]
    client.put(f"/api/projekte/{pid}/einstellungen", json={"start_url": testseite, "crawl_delay": 0})
    assert client.post(f"/projekte/{pid}/crawls").status_code == 200
    for _ in range(50):
        r = client.get(f"/projekte/{pid}/status")
        if r.headers.get("HX-Refresh"):
            break
        time.sleep(0.1)
    assert r.headers.get("HX-Refresh") == "true"
    assert "Website-Zustand" in client.get(f"/projekte/{pid}").text
