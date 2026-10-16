"""Bing Webmaster als zweite Suchmaschine: Quelle (nachgebaute API), Trennung von Google, Zugang, UI."""

from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, gsc
from app.core import gsc_konto, importe, positionen, projekte
from app.db import verbinden
from app.gsc import bing

SCHLUESSEL = "abcdef0123456789abcdef0123456789"


def ms(tag: date) -> str:
    """Datum im Bing-Format, Mitternacht pazifischer Zeit (-0700)."""
    from datetime import datetime, timezone
    utc = datetime(tag.year, tag.month, tag.day, 7, tzinfo=timezone.utc)
    return f"/Date({int(utc.timestamp() * 1000)}-0700)/"


class FakeBing:
    def __init__(self, sites=(("https://ex.de/", True),), status=200):
        self.sites = sites
        self.status = status
        self.anfragen = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.anfragen.append(request)
        assert request.url.params["apikey"] == SCHLUESSEL
        if self.status != 200:
            return httpx.Response(self.status, json={"ErrorCode": 3, "Message": "InvalidApiKey"})
        methode = request.url.path.rsplit("/", 1)[-1]
        if methode == "GetUserSites":
            return httpx.Response(200, json={"d": [{"Url": u, "IsVerified": v} for u, v in self.sites]})
        if methode == "GetQueryStats":
            assert request.url.params["siteUrl"] == "https://ex.de/"
            return httpx.Response(200, json={"d": [
                {"Query": "SEO  Tool", "Date": ms(date(2026, 9, 21)), "Impressions": 120, "Clicks": 6,
                 "AvgImpressionPosition": 4.26, "AvgClickPosition": 3},
                {"Query": "seo tool", "Date": ms(date(2026, 9, 28)), "Impressions": 80, "Clicks": 2,
                 "AvgImpressionPosition": 6, "AvgClickPosition": 5},
                {"Query": "leer", "Date": ms(date(2026, 9, 28)), "Impressions": 0, "Clicks": 0,
                 "AvgImpressionPosition": -1, "AvgClickPosition": -1},
            ]})
        return httpx.Response(404, json={"Message": "unbekannt"})


def quelle(fake) -> bing.BingApiQuelle:
    return bing.BingApiQuelle(SCHLUESSEL, httpx.Client(transport=httpx.MockTransport(fake)))


# ---------- Quelle ----------

def test_bing_datum():
    assert bing.bing_datum("/Date(1316156400000-0700)/") == date(2011, 9, 16)
    assert bing.bing_datum("/Date(1316156400000)/") == date(2011, 9, 16)
    with pytest.raises(gsc.GscFehler):
        bing.bing_datum("2011-09-16")


def test_schluessel_laden(tmp_path):
    with pytest.raises(gsc.GscFehler, match="Kein Bing-Schlüssel"):
        bing.schluessel_laden(tmp_path / "fehlt.txt")
    (tmp_path / "k.txt").write_text("kein schlüssel!")
    with pytest.raises(gsc.GscFehler, match="keinen gültigen"):
        bing.schluessel_laden(tmp_path / "k.txt")
    (tmp_path / "k.txt").write_text(f"  {SCHLUESSEL}\n")
    assert bing.schluessel_laden(tmp_path / "k.txt") == SCHLUESSEL


def test_abrufen_wochenwerte_und_cache():
    fake = FakeBing()
    q = quelle(fake)
    alle = q.abrufen("ex.de", date(2026, 9, 1), date(2026, 9, 30))
    assert alle == [
        {"datum": "2026-09-21", "query": "seo tool", "seite": "", "land": "", "geraet": "", "klicks": 6,
         "impressionen": 120, "position": 4.3},
        {"datum": "2026-09-28", "query": "seo tool", "seite": "", "land": "", "geraet": "", "klicks": 2,
         "impressionen": 80, "position": 6.0},
    ]
    assert q.abrufen("ex.de", date(2026, 9, 28), date(2026, 9, 28))[0]["datum"] == "2026-09-28"
    methoden = [a.url.path.rsplit("/", 1)[-1] for a in fake.anfragen]
    assert methoden.count("GetQueryStats") == 1  # einmal holen, dann tageweise verteilen


@pytest.mark.parametrize("sites, erwartet", [
    ([("http://ex.de/", True), ("https://www.ex.de/", True)], "https://www.ex.de/"),
    ([("https://ex.de/", False), ("http://ex.de/", True)], "http://ex.de/"),
])
def test_property_finden(sites, erwartet):
    assert quelle(FakeBing(sites)).property_finden("ex.de") == erwartet


def test_fehler_ohne_schluessel_in_meldung():
    with pytest.raises(gsc.GscFehler) as e:
        quelle(FakeBing(status=400)).properties()
    assert "InvalidApiKey" in str(e.value) and "Schlüssel prüfen" in str(e.value) and SCHLUESSEL not in str(e.value)

    def kaputt(request):
        raise httpx.ConnectError(f"Fehler bei {request.url}")  # URL enthält den Schlüssel
    with pytest.raises(gsc.GscFehler) as e:
        quelle(kaputt).properties()
    assert "nicht erreichbar" in str(e.value) and SCHLUESSEL not in str(e.value)
    with pytest.raises(gsc.GscFehler, match="Keine bestätigte Website"):
        quelle(FakeBing([("https://ex.de/", False)])).property_finden("ex.de")


# ---------- Trennung Google/Bing, Zugang, Auto-Import ----------

@pytest.fixture
def conn():
    c = verbinden()
    projekte.anlegen(c, "ex.de")
    return c


def test_google_und_bing_getrennt(conn):
    positionen.importieren(conn, 1, "mock", 14, bis=date(2026, 10, 1))
    positionen.importieren(conn, 1, "bing_mock", 14, bis=date(2026, 10, 1))
    assert positionen.bestand(conn, 1)["suchmaschinen"] == ["google", "bing"]
    assert positionen.bestand(conn, 1, "bing")["quellen"] == ["bing_mock"]
    g = positionen.uebersicht(conn, 1, 7)
    b = positionen.uebersicht(conn, 1, 7, suchmaschine="bing")
    assert b["kennzahlen"]["impressionen"] < g["kennzahlen"]["impressionen"]
    assert {t["datum"] for t in b["tage"]} == {"2026-09-28"}  # nur der Montag
    assert all(x["beste_seite"] is None for x in positionen.keywords(conn, 1, 7, suchmaschine="bing")["keywords"])
    with pytest.raises(positionen.PositionenFehler, match="Unbekannte Suchmaschine"):
        positionen.uebersicht(conn, 1, 7, suchmaschine="yahoo")


def test_keine_bing_daten(conn):
    positionen.importieren(conn, 1, "mock", 3, bis=date(2026, 10, 1))
    with pytest.raises(positionen.PositionenFehler, match="Keine Bing-Daten"):
        positionen.uebersicht(conn, 1, suchmaschine="bing")


def test_import_ueber_bing_merkt_website(conn, monkeypatch):
    monkeypatch.setitem(gsc.QUELLEN, "bing", lambda: quelle(FakeBing()))
    r = positionen.importieren(conn, 1, "bing", 30, bis=date(2026, 9, 30))
    assert (r["property"], r["zeilen"]) == ("https://ex.de/", 2)
    assert gsc_konto.property_holen(conn, 1, "bing") == "https://ex.de/"
    assert gsc_konto.property_holen(conn, 1, "gsc") is None


def test_zugang_bing(conn, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "BING_SCHLUESSEL", tmp_path / "bing.txt")
    s = gsc_konto.status(conn, 1, "bing")
    assert not s["schluessel_da"] and s["name"] == "Bing Webmaster Tools"
    (tmp_path / "bing.txt").write_text(SCHLUESSEL)
    s = gsc_konto.status(conn, 1, "bing")
    assert s["schluessel_da"] and SCHLUESSEL not in str(s)
    assert gsc_konto.property_setzen(conn, 1, "https://ex.de", "bing") == "https://ex.de/"
    with pytest.raises(gsc.GscFehler, match="http"):
        gsc_konto.property_setzen(conn, 1, "sc-domain:ex.de", "bing")
    with pytest.raises(gsc.GscFehler, match="Unbekannte Quelle"):
        gsc_konto.status(conn, 1, "mock")


def test_alte_gsc_property_wird_uebernommen(test_db):
    conn = verbinden()
    projekte.anlegen(conn, "ex.de")
    conn.execute("INSERT INTO gsc_einstellungen (projekt_id, property) VALUES (1, 'sc-domain:ex.de')")
    conn.execute("INSERT INTO gsc_auto (projekt_id, quelle) VALUES (1, 'mock')")
    conn.commit()
    conn.close()
    conn = verbinden()  # Schema läuft erneut und übernimmt die alten Einträge
    assert gsc_konto.property_holen(conn, 1) == "sc-domain:ex.de"
    assert importe.auto_holen(conn, 1) == {"google": "mock", "bing": None}
    assert conn.execute("SELECT COUNT(*) FROM gsc_einstellungen").fetchone()[0] == 0


def test_bing_auto_import_pause(conn):
    importe.auto_setzen(conn, 1, "bing_mock")
    heute = date.today()
    erster = importe.auto_lauf(conn, heute)
    assert [(i["quelle"], i["status"]) for i in erster] == [("bing_mock", "fertig")]
    assert importe.faellig(conn, heute) == []  # Wochenwerte: nicht alle 30 Min. erneut holen


# ---------- UI ----------

def test_ui_bing():
    from app.web import app
    client = TestClient(app)
    p = client.post("/api/projekte", json={"domain": "ex.de"}).json()["id"]
    seite = client.get(f"/projekte/{p}/positionen").text
    assert "Zugang Bing Webmaster Tools" in seite and "Zugang Search Console" in seite
    client.post(f"/api/projekte/{p}/positionen/import", json={"quelle": "bing_mock", "tage": 28, "warten": True})
    seite = client.get(f"/projekte/{p}/positionen?suchmaschine=bing").text
    assert "Wochenwerte" in seite and "Testdaten Bing" in seite and '<select name="geraet"' not in seite
    assert "Keine Search-Console-Daten" in client.get(f"/projekte/{p}/positionen").text
    csv = client.get(f"/projekte/{p}/positionen/keywords.csv?suchmaschine=bing").text
    assert "Bing, " in csv.splitlines()[1]
    assert client.get(f"/api/projekte/{p}/positionen?suchmaschine=bing").json()["suchmaschine"] == "bing"
    assert "Bing: Testdaten" in client.post(f"/projekte/{p}/positionen/auto",
                                            data={"quelle": "bing_mock", "suchmaschine": "bing"}).text
