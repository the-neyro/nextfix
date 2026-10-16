"""Phase 4: CSV-Export der Suchbegriffe und Länderfilter."""

import csv
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core import export, positionen, projekte, tracking
from app.db import verbinden
from app.gsc.laender import land_name
from tests.test_positionen import FesteQuelle, laden, zeile


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setitem(positionen.gsc.QUELLEN, "fest", FesteQuelle)
    monkeypatch.setitem(positionen.gsc.SUCHMASCHINE, "fest", "google")
    c = verbinden()
    projekte.anlegen(c, "ex.de")
    return c


def lesen(text: str) -> list[list[str]]:
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text[1:]), delimiter=";"))


def test_csv_inhalt_und_format(conn):
    laden(conn, [zeile("2026-09-30", "seo tool", position=8.5), zeile("2026-10-01", "seo tool", position=4.25),
                 zeile("2026-10-01", "neu", position=12)])
    tracking.hinzufuegen(conn, 1, ["seo tool"], ["kern"])
    zeilen = lesen(export.keywords_csv(conn, 1, tage=1, auswahl="alle"))
    kopf, daten = zeilen[0], {z[0]: z for z in zeilen[1:]}
    assert kopf[:4] == ["Suchbegriff", "Position", "Position vorher", "Änderung (+ = besser)"]
    s = dict(zip(kopf, daten["seo tool"]))
    assert (s["Position"], s["Position vorher"], s["Änderung (+ = besser)"]) == ("4,2", "8,5", "4,3")
    assert (s["Klicks"], s["Impressionen"], s["CTR %"], s["Getrackt"], s["Tags"]) == ("10", "100", "10", "ja", "kern")
    assert s["Zeitraum/Filter"].startswith("Google, 2026-10-01 bis 2026-10-01") and "alle Suchbegriffe" in s["Zeitraum/Filter"]
    n = dict(zip(kopf, daten["neu"]))
    assert n["Position vorher"] == "" and n["Status"] == "neu" and n["Getrackt"] == ""


def test_csv_folgt_filtern(conn):
    laden(conn, [zeile("2026-10-01", "a"), zeile("2026-10-01", "b")])
    tracking.hinzufuegen(conn, 1, ["b"], ["x"])
    assert [z[0] for z in lesen(export.keywords_csv(conn, 1, 1, tag="x"))[1:]] == ["b"]
    assert len(lesen(export.keywords_csv(conn, 1, 1, auswahl="alle", suche="a"))) == 2


def test_laenderfilter(conn):
    laden(conn, [zeile("2026-10-01", "a", impressionen=100),
                 {**zeile("2026-10-01", "a", impressionen=30, position=9), "land": "aut"},
                 {**zeile("2026-10-01", "nur at", impressionen=5), "land": "aut"}])
    assert positionen.bestand(conn, 1)["laender"] == ["aut", "deu"]
    deu = positionen.uebersicht(conn, 1, 1, land="deu")
    aut = positionen.uebersicht(conn, 1, 1, land="AUT")
    alle = positionen.uebersicht(conn, 1, 1)
    assert (deu["kennzahlen"]["impressionen"], aut["kennzahlen"]["impressionen"],
            alle["kennzahlen"]["impressionen"]) == (100, 35, 135)
    assert {x["query"] for x in positionen.keywords(conn, 1, 1, land="aut")["keywords"]} == {"a", "nur at"}
    assert "Österreich" in lesen(export.keywords_csv(conn, 1, 1, land="aut"))[1][-1]
    assert land_name("aut") == "Österreich" and land_name("xyz") == "XYZ"


def test_mock_hat_mehrere_laender():
    from app.gsc.mock import MockQuelle
    zeilen = MockQuelle().abrufen("ex.de", date(2026, 9, 1), date(2026, 9, 1))
    impressionen = {}
    for z in zeilen:
        impressionen[z["land"]] = impressionen.get(z["land"], 0) + z["impressionen"]
    assert set(impressionen) == {"deu", "aut", "che"}
    assert impressionen["deu"] > impressionen["aut"] > 0


def test_ui_und_api():
    from app.web import app
    client = TestClient(app)
    p = client.post("/api/projekte", json={"domain": "ex.de"}).json()["id"]
    client.post(f"/api/projekte/{p}/positionen/import", json={"quelle": "mock", "tage": 20, "warten": True})
    seite = client.get(f"/projekte/{p}/positionen?land=aut").text
    assert "Österreich" in seite and "Schweiz" in seite and "keywords.csv?suchmaschine=google&amp;tage=28" in seite and "land=aut" in seite
    r = client.get(f"/projekte/{p}/positionen/keywords.csv?tage=7&land=che")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "Schweiz" in lesen(r.text)[1][-1]
    assert lesen(client.get(f"/api/projekte/{p}/positionen/keywords.csv?tage=7").text)[0][0] == "Suchbegriff"
    assert client.get(f"/projekte/{p}/positionen/keywords.csv?sortierung=quatsch").status_code == 400
    assert client.get(f"/projekte/{p}/positionen/verlauf", params={"query": "ex", "land": "aut"}).status_code == 200
