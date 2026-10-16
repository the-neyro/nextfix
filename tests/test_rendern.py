"""JavaScript ausführen: Crawl wertet das gerenderte DOM aus und merkt sich die Wörter ohne JavaScript."""

import pytest

from app.core import audit, projekte
from app.crawler import crawler
from app.db import verbinden

ZUSATZ = " ".join(f"jswort{i}" for i in range(600))


class FakeRenderer:
    """Hängt an /gut viel Text und einen Link auf /verwaist an (sonst nur über die Sitemap erreichbar)."""
    gerendert: list[str] = []

    def __init__(self, user_agent):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def rendern(self, url):
        import httpx
        FakeRenderer.gerendert.append(url)
        html = httpx.get(url).text
        if url.endswith("/gut"):
            html = html.replace("</body>", f'<p>{ZUSATZ}</p><a href="/verwaist">Verwaist</a></body>')
        return html


def _crawl(testseite, **einst):
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1").id
    audit.einstellungen_setzen(conn, p, start_url=testseite, crawl_delay=0, **einst)
    return conn, audit.crawl_starten(conn, p, warten=True)["id"]


def _seite(conn, crawl_id, url):
    return conn.execute("SELECT woerter, woerter_roh FROM seiten WHERE crawl_id=? AND url=?", (crawl_id, url)).fetchone()


def test_gerendertes_dom_wird_ausgewertet(testseite, monkeypatch):
    monkeypatch.setattr(crawler, "RENDERER_FABRIK", FakeRenderer)
    conn, c = _crawl(testseite, js_rendern=True)
    assert audit.crawl_holen(conn, c)["status"] == "fertig"
    assert conn.execute("SELECT js_rendern FROM crawls WHERE id=?", (c,)).fetchone()[0] == 1
    gut = _seite(conn, c, testseite + "gut")
    assert gut["woerter_roh"] < 300 and gut["woerter"] > 800
    assert _seite(conn, c, testseite + "verwaist") is not None   # Link aus dem gerenderten DOM gefolgt
    treffer = {t["url"] for t in audit.issue_details(conn, c, "inhalt_nur_per_js")["treffer"]}
    assert treffer == {testseite + "gut"}


def test_ohne_js_rendern_kein_renderer(testseite, monkeypatch):
    FakeRenderer.gerendert = []
    monkeypatch.setattr(crawler, "RENDERER_FABRIK", FakeRenderer)
    conn, c = _crawl(testseite)
    assert FakeRenderer.gerendert == []
    assert _seite(conn, c, testseite + "gut")["woerter_roh"] is None
    assert not audit.issue_details(conn, c, "inhalt_nur_per_js")["treffer"]


def test_einstellung_ueber_ui():
    from fastapi.testclient import TestClient
    from app.web import app
    conn = verbinden()
    p = projekte.anlegen(conn, "ex.de").id
    client = TestClient(app)
    assert 'name="js_rendern"' in client.get(f"/projekte/{p}/einstellungen").text
    daten = {"start_url": "https://ex.de/", "seitenlimit": "50", "crawl_delay": "0.5", "user_agent": "x",
             "robots_beachten": "1", "js_rendern": "1"}
    assert "Gespeichert" in client.post(f"/projekte/{p}/einstellungen", data=daten).text
    assert audit.einstellungen_holen(conn, p)["js_rendern"] is True


def test_echtes_chromium_fuehrt_javascript_aus(testseite):
    pytest.importorskip("playwright")
    from app.crawler.rendern import Renderer
    try:
        with Renderer("SeoToolBot/0.1 (+lokal)") as r:
            html = r.rendern(testseite + "js")
    except Exception as fehler:  # Chromium nicht installiert
        pytest.skip(f"Chromium fehlt: {fehler}")
    assert html and "inhalt299" in html and 'href="/gut"' in html
    conn, c = _crawl(testseite + "js", js_rendern=True, seitenlimit=1)
    s = _seite(conn, c, testseite + "js")
    assert s["woerter_roh"] < 10 and s["woerter"] >= 300
    assert audit.issue_details(conn, c, "inhalt_nur_per_js")["treffer"]


# ---------- Hinweis: Seite sieht nach JavaScript-App aus ----------

def test_parser_erkennt_leeren_app_container():
    from app.crawler.parser import zerlegen
    skript = "<script src='/app.js'></script>"
    assert zerlegen(f"<html><body><div id='root'></div>{skript}</body></html>", "https://ex.de/").js_app == "#root"
    assert zerlegen(f"<html><body><app-root></app-root>{skript}</body></html>", "https://ex.de/").js_app == "app-root"
    voll = " ".join(["Text"] * 50)   # Server-Rendering (z. B. Next.js): Container schon gefüllt
    assert zerlegen(f"<html><body><div id='__next'><p>{voll}</p></div>{skript}</body></html>", "https://ex.de/").js_app is None
    assert zerlegen("<html><body><div id='app'></div></body></html>", "https://ex.de/").js_app is None   # ohne Skript


def test_hinweis_ohne_js_rendern(testseite):
    from fastapi.testclient import TestClient
    from app.web import app
    conn, c = _crawl(testseite + "js", seitenlimit=1)
    treffer = audit.issue_details(conn, c, "js_app_ohne_rendern")["treffer"]
    assert [t["url"] for t in treffer] == [testseite + "js"] and "#app" in treffer[0]["detail"]
    assert audit.uebersicht(conn, c)["js_hinweis"] == 1
    seite = TestClient(app).get(f"/projekte/{audit.crawl_holen(conn, c)['projekt_id']}").text
    assert "Diese Website baut sich per JavaScript auf" in seite and "JavaScript ausführen" in seite


def test_kein_hinweis_mit_js_rendern(testseite, monkeypatch):
    class Gefuellt(FakeRenderer):
        def rendern(self, url):
            return f"<html><body><div id='app'><p>{ZUSATZ}</p></div><script></script></body></html>"
    monkeypatch.setattr(crawler, "RENDERER_FABRIK", Gefuellt)
    conn, c = _crawl(testseite + "js", seitenlimit=1, js_rendern=True)
    assert not audit.issue_details(conn, c, "js_app_ohne_rendern")["treffer"]
    assert audit.uebersicht(conn, c)["js_hinweis"] == 0
