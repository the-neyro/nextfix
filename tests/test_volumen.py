"""Phase 5: Suchvolumen aus Bing (GetKeywordStats) für Keyword-Ideen."""

import time
from datetime import date, datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import keywords, projekte
from app.db import verbinden
from app.gsc import bing
from app.keywords import suggest, volumen
from tests.test_keywords import FakeSuggest

SCHLUESSEL = "abcdef0123456789abcdef0123456789"


def bing_datum(tag: date) -> str:
    return f"/Date({int(datetime(tag.year, tag.month, tag.day, 7, tzinfo=timezone.utc).timestamp() * 1000)}-0700)/"


class FakeBingKeywords:
    def __init__(self, status=200):
        self.status = status
        self.anfragen = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        p = request.url.params
        self.anfragen.append(p["q"])
        assert request.url.path.endswith("/GetKeywordStats") and p["apikey"] == SCHLUESSEL
        assert (p["country"], p["language"]) == ("de", "de-DE")
        if self.status != 200:
            return httpx.Response(self.status, json={"Message": "ThrottleUser"})
        if p["q"] == "unbekannt":
            return httpx.Response(200, json={"d": []})
        # absichtlich unsortiert: zwei Wochen
        return httpx.Response(200, json={"d": [
            {"Query": p["q"], "Date": bing_datum(date(2026, 9, 28)), "Impressions": 30, "BroadImpressions": 90},
            {"Query": p["q"], "Date": bing_datum(date(2026, 9, 21)), "Impressions": 10, "BroadImpressions": 40},
        ]})


def bing_volumen(conn, fake):
    q = bing.BingApiQuelle(SCHLUESSEL, httpx.Client(transport=httpx.MockTransport(fake)))
    return volumen.BingVolumen(conn, "de", "de", quelle=q, pause=0)


@pytest.fixture
def conn():
    c = verbinden()
    projekte.anlegen(c, "ex.de")
    return c


def test_monatswert():
    assert volumen.monatswert([]) is None
    assert volumen.monatswert([10, 30]) == round(20 * 52 / 12)
    assert volumen.monatswert([1000] * 10 + [12] * 13) == 52  # nur die letzten 13 Wochen


def test_bing_volumen_mit_cache(conn):
    fake = FakeBingKeywords()
    v = bing_volumen(conn, fake)
    assert v.holen("seo tool") == {"monat": round(20 * 52 / 12), "verlauf": [10, 30]}  # nach Datum sortiert
    assert v.holen("unbekannt") == {"monat": None, "verlauf": []}
    assert v.holen("seo tool")["monat"] == 87 and fake.anfragen == ["seo tool", "unbekannt"]  # Cache


def test_bing_fehler(conn):
    with pytest.raises(volumen.GscFehler, match="ThrottleUser"):
        bing_volumen(conn, FakeBingKeywords(status=400)).holen("seo")


def test_mock_deterministisch(conn):
    a = volumen.BingVolumenMock(conn).holen("seo tool kostenlos")
    conn.execute("DELETE FROM volumen_cache")
    assert volumen.BingVolumenMock(conn).holen("seo tool kostenlos") == a


@pytest.fixture
def recherche(conn, monkeypatch):
    f = FakeSuggest()
    monkeypatch.setattr(keywords, "SUGGEST_FABRIK", lambda c, s, l: suggest.Suggest(
        c, s, l, client=httpx.Client(transport=httpx.MockTransport(f)), pause=0))
    return keywords.starten(conn, 1, "seo tool", warten=True)["id"]


def test_volumen_fuer_recherche(conn, recherche, monkeypatch):
    fake = FakeBingKeywords()
    monkeypatch.setitem(keywords.VOLUMEN_QUELLEN, "bing",
                        lambda c, land, sprache: bing_volumen(c, fake))
    r = keywords.volumen_starten(conn, recherche, "bing", limit=5, warten=True)
    r = keywords.holen(conn, recherche)
    assert (r["volumen_status"], r["volumen_fertig"], r["volumen_gesamt"]) == ("fertig", 5, 5)
    d = keywords.ideen(conn, recherche, sortierung="volumen")
    oben = d["ideen"][:5]
    assert all(i["volumen"] == 87 and i["trend"] == [10, 30] and i["volumen_quelle"] == "bing" for i in oben)
    assert d["ideen"][5]["volumen"] is None
    # zweiter Lauf: nur die noch offenen Ideen
    keywords.volumen_starten(conn, recherche, "bing", limit=3, warten=True)
    assert len(fake.anfragen) == 8 and keywords.ideen(conn, recherche, sortierung="volumen")["ideen"][7]["volumen"] == 87


def test_volumen_fehler_und_eingaben(conn, recherche, monkeypatch):
    monkeypatch.setitem(keywords.VOLUMEN_QUELLEN, "bing",
                        lambda c, land, sprache: bing_volumen(c, FakeBingKeywords(status=400)))
    keywords.volumen_starten(conn, recherche, "bing", warten=True)
    r = keywords.holen(conn, recherche)
    assert r["volumen_status"] == "fehler" and "ThrottleUser" in r["volumen_fehler"]
    with pytest.raises(keywords.KeywordFehler, match="Volumen-Quelle"):
        keywords.volumen_starten(conn, recherche, "google")
    with pytest.raises(keywords.KeywordFehler, match="limit"):
        keywords.volumen_starten(conn, recherche, "bing_mock", limit=0)
    conn.execute("UPDATE recherchen SET volumen_status = 'laeuft', volumen_lebenszeichen = datetime('now')")
    conn.commit()
    with pytest.raises(keywords.KeywordFehler, match="läuft noch"):
        keywords.volumen_starten(conn, recherche, "bing_mock")


def test_ui_und_api(monkeypatch):
    f = FakeSuggest()
    monkeypatch.setattr(keywords, "SUGGEST_FABRIK", lambda c, s, l: suggest.Suggest(
        c, s, l, client=httpx.Client(transport=httpx.MockTransport(f)), pause=0))
    from app.web import app
    client = TestClient(app)
    p = client.post("/api/projekte", json={"domain": "ex.de"}).json()["id"]
    rid = client.post(f"/api/projekte/{p}/keywords/recherchen", json={"seed": "seo", "warten": True}).json()["id"]
    seite = client.get(f"/recherchen/{rid}").text
    assert "Bing/Monat" in seite and "Schlüssel fehlt" in seite
    r = client.post(f"/recherchen/{rid}/volumen", data={"quelle": "bing_mock"})
    assert r.status_code == 200 and 'id="volumen-status"' in r.text
    ende = time.time() + 10
    while "HX-Refresh" not in (a := client.get(f"/recherchen/{rid}/volumen-status")).headers:
        assert time.time() < ende
        time.sleep(0.05)
    assert "Volumen für" in a.text
    seite = client.get(f"/recherchen/{rid}?sortierung=volumen").text
    assert "<polyline" in seite and 'title="Testwert"' in seite
    api = client.post(f"/api/keywords/recherchen/{rid}/volumen", json={"quelle": "bing_mock", "warten": True}).json()
    assert api["volumen_status"] == "fertig"
    assert client.post(f"/api/keywords/recherchen/{rid}/volumen", json={"quelle": "x"}).status_code == 400
