"""Phase 4: Position Tracking (Mock-Quelle, Auswertung, REST, UI)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core import positionen, projekte
from app.db import verbinden
from app.gsc.ctr import erwartete_ctr
from app.gsc.mock import MockQuelle

BIS = date(2026, 10, 1)


def zeile(datum, query, seite="/a", position=5.0, impressionen=100, klicks=10, geraet="MOBILE"):
    return {"datum": datum, "query": query, "seite": "https://ex.de" + seite, "land": "deu", "geraet": geraet,
            "klicks": klicks, "impressionen": impressionen, "position": position}


class FesteQuelle:
    """Testquelle mit vorgegebenen Zeilen."""
    name = "fest"
    zeilen: list[dict] = []

    def abrufen(self, domain, von, bis, property=None):
        return [z for z in self.zeilen if von.isoformat() <= z["datum"] <= bis.isoformat()]


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setitem(positionen.gsc.QUELLEN, "fest", FesteQuelle)
    monkeypatch.setitem(positionen.gsc.SUCHMASCHINE, "fest", "google")
    c = verbinden()
    projekte.anlegen(c, "ex.de")
    return c


def laden(conn, zeilen, tage=4):
    FesteQuelle.zeilen = zeilen
    return positionen.importieren(conn, 1, "fest", tage, bis=BIS)


# ---------- Mock-Quelle ----------

def test_mock_deterministisch_und_plausibel():
    a = MockQuelle().abrufen("ex.de", date(2026, 9, 1), date(2026, 9, 3))
    b = MockQuelle().abrufen("ex.de", date(2026, 9, 2), date(2026, 9, 2))
    assert [z for z in a if z["datum"] == "2026-09-02"] == b  # überlappende Abrufe gleich
    assert all(z["impressionen"] > 0 and 0 <= z["klicks"] <= z["impressionen"] and z["position"] >= 1 for z in a)
    assert {"ex", "ex erfahrungen"} <= {z["query"] for z in a}


def test_import_mock_und_ersetzen(conn):
    r = positionen.importieren(conn, 1, "mock", 10, bis=BIS)
    assert r["von"] == "2026-09-22" and r["zeilen"] > 0
    positionen.importieren(conn, 1, "mock", 10, bis=BIS)  # gleicher Zeitraum: keine Dubletten
    assert positionen.bestand(conn, 1)["zeilen"] == r["zeilen"]
    assert positionen.daten_loeschen(conn, 1, "mock") == r["zeilen"]
    assert positionen.bestand(conn, 1) is None


def test_import_fehler(conn):
    with pytest.raises(positionen.PositionenFehler, match="Unbekannte Quelle"):
        positionen.importieren(conn, 1, "gibtsnicht")
    with pytest.raises(positionen.PositionenFehler):
        positionen.importieren(conn, 1, "mock", 0)
    with pytest.raises(positionen.PositionenFehler, match="zuerst importieren"):
        positionen.uebersicht(conn, 1)


# ---------- Auswertung ----------

def test_keywords_gewichtete_position_und_aenderung(conn):
    laden(conn, [
        # Vorzeitraum (2 Tage): Position 10
        zeile("2026-09-28", "seo", position=10), zeile("2026-09-29", "seo", position=10),
        # Zeitraum: 300 Impressionen auf Pos. 2, 100 auf Pos. 6 → gewichtet 3,0
        zeile("2026-09-30", "seo", position=2, impressionen=300), zeile("2026-10-01", "seo", position=6),
        zeile("2026-09-28", "alt", position=30),
        zeile("2026-10-01", "neu", position=15),
    ])
    k = {x["query"]: x for x in positionen.keywords(conn, 1, tage=2)["keywords"]}
    assert k["seo"]["position"] == 3.0 and k["seo"]["position_vorher"] == 10.0
    assert k["seo"]["aenderung"] == 7.0  # positiv = besser
    assert k["seo"]["klicks"] == 20 and k["seo"]["ctr"] == 5.0
    assert k["neu"]["status"] == "neu" and k["alt"]["status"] == "verloren"
    assert k["alt"]["position"] is None and k["alt"]["aenderung"] is None


def test_uebersicht_kennzahlen(conn):
    laden(conn, [
        zeile("2026-09-30", "a", position=1), zeile("2026-10-01", "a", position=1),
        zeile("2026-09-30", "b", position=12), zeile("2026-10-01", "b", position=12),
        zeile("2026-09-28", "a", position=4), zeile("2026-09-28", "b", position=12),
        # Kannibalisierung: zweite Seite mit 40 % der Impressionen
        zeile("2026-10-01", "b", seite="/b2", position=18, impressionen=150),
    ])
    u = positionen.uebersicht(conn, 1, tage=2)
    k = u["kennzahlen"]
    # b: (12·100 + 12·100 + 18·150) / 350 = 14,6
    assert k["keywords"] == 2 and k["sichtbarkeit"] == round(100 * (1 + erwartete_ctr(14.6) / erwartete_ctr(1)) / 2, 1)
    assert u["verteilung"] == {"top3": 1, "top10": 1, "top20": 2, "top100": 2}
    assert [x["query"] for x in u["gewinner"]] == ["a"]
    assert [x["query"] for x in u["verlierer"]] == ["b"]  # 12 → 14,6
    assert [x["query"] for x in u["striking"]] == ["b"] and u["striking"][0]["position"] == 14.6
    assert u["kannibalisierung"][0]["query"] == "b"
    assert [s["anteil"] for s in u["kannibalisierung"][0]["seiten"]] == [57, 43]
    assert [t["datum"] for t in u["tage"]] == ["2026-09-30", "2026-10-01"]


def test_sichtbarkeit_grenzen():
    assert positionen._sichtbarkeit([1, 1]) == 100.0
    assert positionen._sichtbarkeit([1, None]) == 50.0
    assert positionen._sichtbarkeit([]) == 0.0


def test_filter_geraet_und_sortierung(conn):
    laden(conn, [zeile("2026-10-01", "a", geraet="DESKTOP", impressionen=50),
                 zeile("2026-10-01", "b", impressionen=500, position=20)])
    assert [x["query"] for x in positionen.keywords(conn, 1, 1, geraet="desktop")["keywords"]] == ["a"]
    assert [x["query"] for x in positionen.keywords(conn, 1, 1, sortierung="position")["keywords"]] == ["a", "b"]
    assert [x["query"] for x in positionen.keywords(conn, 1, 1)["keywords"]] == ["b", "a"]
    with pytest.raises(positionen.PositionenFehler):
        positionen.keywords(conn, 1, 1, geraet="FERNSEHER")
    with pytest.raises(positionen.PositionenFehler):
        positionen.keywords(conn, 1, 1, sortierung="quatsch")


def test_keyword_verlauf(conn):
    laden(conn, [zeile("2026-09-30", "a", position=3), zeile("2026-10-01", "a", position=5),
                 zeile("2026-10-01", "a", seite="/x", position=9)])
    v = positionen.keyword_verlauf(conn, 1, "a", tage=4)
    assert [t["position"] for t in v["tage"]] == [3.0, 7.0]
    assert set(v["seiten"]) == {"https://ex.de/a", "https://ex.de/x"}
    with pytest.raises(positionen.PositionenFehler, match="nicht gefunden"):
        positionen.keyword_verlauf(conn, 1, "fehlt")


# ---------- REST und UI ----------

def test_api_und_ui():
    from app.web import app
    client = TestClient(app)
    p = client.post("/api/projekte", json={"domain": "ex.de"}).json()["id"]
    assert client.get(f"/api/projekte/{p}/positionen").status_code == 400
    assert "Testdaten laden" in client.get(f"/projekte/{p}/positionen").text
    r = client.post(f"/api/projekte/{p}/positionen/import", json={"quelle": "mock", "tage": 60, "warten": True})
    assert r.status_code == 200 and r.json()["zeilen"] > 0
    u = client.get(f"/api/projekte/{p}/positionen?tage=28").json()
    assert u["kennzahlen"]["keywords"] > 10
    kw = client.get(f"/api/projekte/{p}/positionen/keywords?sortierung=klicks").json()["keywords"]
    assert kw[0]["klicks"] >= kw[-1]["klicks"]
    assert client.get(f"/api/projekte/{p}/positionen/verlauf", params={"query": "ex"}).json()["tage"]
    seite = client.get(f"/projekte/{p}/positionen?tage=7&geraet=MOBILE&sortierung=aenderung")
    assert seite.status_code == 200 and "Sichtbarkeit" in seite.text and "Mehrere Seiten für einen Suchbegriff" in seite.text
    assert "beste Ø-Position" in client.get(f"/projekte/{p}/positionen/verlauf", params={"query": "seo check"}).text
    assert client.delete(f"/api/projekte/{p}/positionen?quelle=mock").json()["geloescht"] > 0
