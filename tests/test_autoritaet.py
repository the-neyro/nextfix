"""Domain-Autorität (Open PageRank): Client, Zwischenspeicher, Anzeige. Ohne echte Anfragen."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.core import autoritaet, projekte, teilnoten
from app.db import verbinden
from app.linkdaten import openpagerank as opr

WERTE = {"beispiel.de": ("2.61", "1234567"), "mitbewerber.de": ("3.4", "456789")}


class FakeApi:
    """Nachbau von getPageRank. Merkt sich die abgefragten Domains."""
    def __init__(self):
        self.abgefragt: list[list[str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("API-OPR") != "testschluessel123456":
            return httpx.Response(401, json={"status_code": 401, "error": "Invalid API key.", "response": []})
        domains = request.url.params.get_list("domains[]")
        self.abgefragt.append(domains)
        antwort = [{"status_code": 200, "error": "", "page_rank_decimal": float(WERTE[d][0]), "rank": WERTE[d][1],
                    "domain": d} if d in WERTE else
                   {"status_code": 404, "error": "Domain not found", "page_rank_decimal": 0, "rank": None, "domain": d}
                   for d in domains]
        return httpx.Response(200, json={"status_code": 200, "response": antwort, "last_updated": "1st Sep 2026"})


@pytest.fixture
def api(tmp_path, monkeypatch):
    datei = tmp_path / "opr.txt"
    datei.write_text("testschluessel123456\n")
    monkeypatch.setattr(config, "OPR_SCHLUESSEL", datei)
    fake = FakeApi()
    echte_abfrage = opr.abfragen
    monkeypatch.setattr(opr, "abfragen", lambda domains, schluessel=None, client=None:
                        echte_abfrage(domains, schluessel, httpx.Client(transport=httpx.MockTransport(fake))))
    return fake


def test_domain_normal():
    assert autoritaet.domain_normal("WWW.Beispiel.de") == "beispiel.de"
    assert autoritaet.domain_normal("beispiel.de:8080") == "beispiel.de"
    assert autoritaet.domain_normal("127.0.0.1") is None and autoritaet.domain_normal("localhost") is None


def test_abruf_und_zwischenspeicher(api):
    conn = verbinden()
    w = autoritaet.aktualisieren(conn, ["www.beispiel.de", "mitbewerber.de", "unbekannt.de", "127.0.0.1"])
    assert w["www.beispiel.de"]["wert"] == 2.61 and w["www.beispiel.de"]["rang"] == 1234567
    assert w["unbekannt.de"]["wert"] is None and w["unbekannt.de"]["fehler"] == "Domain not found"
    assert "127.0.0.1" not in w
    assert api.abgefragt == [["beispiel.de", "mitbewerber.de", "unbekannt.de"]]
    autoritaet.aktualisieren(conn, ["beispiel.de", "mitbewerber.de"])    # frisch gespeichert → keine Anfrage
    assert len(api.abgefragt) == 1
    autoritaet.aktualisieren(conn, ["beispiel.de"], neu=True)
    assert api.abgefragt[-1] == ["beispiel.de"]


def test_falscher_schluessel(api, tmp_path, monkeypatch):
    datei = tmp_path / "falsch.txt"
    datei.write_text("falscherschluessel9999")
    monkeypatch.setattr(config, "OPR_SCHLUESSEL", datei)
    with pytest.raises(opr.OprFehler, match="Invalid API key"):
        autoritaet.aktualisieren(verbinden(), ["beispiel.de"])


def test_ohne_schluessel_still(api, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OPR_SCHLUESSEL", tmp_path / "fehlt.txt")
    conn = verbinden()
    autoritaet.still_aktualisieren(conn, ["beispiel.de"])   # kein Fehler, keine Anfrage
    assert api.abgefragt == []


def test_teilnote_und_vergleich(api):
    conn = verbinden()
    eigen = projekte.anlegen(conn, "beispiel.de").id
    projekte.anlegen(conn, "mitbewerber.de")
    c = conn.execute("INSERT INTO crawls (projekt_id, start_url, status) VALUES (?, 'https://beispiel.de/', 'fertig')",
                     (eigen,)).lastrowid
    conn.commit()
    note = next(n for n in teilnoten.liste(conn, eigen, c) if n["name"] == "Autorität")
    assert note["wert"] is None and note["hinweis"] == "noch keine Daten"
    autoritaet.aktualisieren(conn, ["beispiel.de", "mitbewerber.de"])
    note = next(n for n in teilnoten.liste(conn, eigen, c) if n["name"] == "Autorität")
    assert note["wert"] == 2.61 and note["skala"] == 10
    assert [z["domain"] for z in autoritaet.vergleich(conn)] == ["mitbewerber.de", "beispiel.de"]


def test_oberflaeche_und_api(api):
    from app.web import app
    conn = verbinden()
    projekte.anlegen(conn, "beispiel.de")
    projekte.anlegen(conn, "mitbewerber.de")
    client = TestClient(app)
    assert "Werte abrufen" in client.get("/").text
    teil = client.post("/autoritaet").text
    assert "Autorität im Vergleich" in teil and "3,4" in teil and "2,6" in teil
    assert [z["wert"] for z in client.get("/api/autoritaet").json()] == [3.4, 2.61]
    assert client.post("/api/autoritaet", json={"domains": ["unbekannt.de"]}).json()["unbekannt.de"]["wert"] is None


def test_ohne_schluessel_hinweis_in_oberflaeche():
    from app.web import app
    assert "Nicht verbunden" in TestClient(app).get("/").text
