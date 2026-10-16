"""Phase 4: Importe im Hintergrund und täglicher Auto-Import."""

import time
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import config
from app.core import importe, positionen, projekte
from app.db import verbinden

HEUTE = date(2026, 10, 10)  # → Ziel-Ende 2026-10-07 (Verzug 3 Tage)


@pytest.fixture
def conn():
    c = verbinden()
    projekte.anlegen(c, "ex.de")
    return c


def warten_bis_fertig(conn, import_id, sekunden=10):
    ende = time.time() + sekunden
    while time.time() < ende:
        imp = importe.holen(conn, import_id)
        if imp["status"] != "laeuft":
            return imp
        time.sleep(0.05)
    raise AssertionError("Import nicht fertig geworden")


def test_import_blockierend_mit_fortschritt(conn):
    imp = importe.starten(conn, 1, "mock", 5, bis=date(2026, 10, 1), warten=True)
    assert imp["status"] == "fertig" and imp["ausloeser"] == "hand"
    assert (imp["von"], imp["bis"], imp["tage_gesamt"], imp["tage_fertig"]) == ("2026-09-27", "2026-10-01", 5, 5)
    assert imp["zeilen"] == positionen.bestand(conn, 1)["zeilen"] > 0


def test_import_im_hintergrund(conn):
    imp = importe.starten(conn, 1, "mock", 20, bis=date(2026, 10, 1))
    fertig = warten_bis_fertig(conn, imp["id"])
    assert fertig["status"] == "fertig" and fertig["tage_fertig"] == 20
    assert importe.letzter(conn, 1)["id"] == imp["id"]


def test_nur_ein_import_gleichzeitig_und_verwaiste(conn):
    conn.execute("INSERT INTO gsc_importe (projekt_id, quelle, von, bis, tage_gesamt, lebenszeichen)"
                 " VALUES (1, 'mock', '2026-09-01', '2026-09-02', 2, datetime('now'))")
    conn.commit()
    with pytest.raises(importe.ImportFehler, match="läuft noch"):
        importe.starten(conn, 1, "mock", 2)
    # Lebenszeichen zu alt → gilt als abgebrochen, neuer Import darf starten
    conn.execute("UPDATE gsc_importe SET lebenszeichen = datetime('now', '-10 minutes')")
    conn.commit()
    assert importe.starten(conn, 1, "mock", 2, warten=True)["status"] == "fertig"
    alt = importe.liste(conn, 1)[-1]
    assert alt["status"] == "fehler" and "kein Lebenszeichen" in alt["fehler_text"]


def test_fehler_landet_im_import(conn, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GSC_SCHLUESSEL", tmp_path / "fehlt.json")
    imp = importe.starten(conn, 1, "gsc", 3, warten=True)
    assert imp["status"] == "fehler" and "Kein Schlüssel" in imp["fehler_text"]
    with pytest.raises(importe.ImportFehler, match="Unbekannte Quelle"):
        importe.starten(conn, 1, "gibtsnicht")
    with pytest.raises(importe.ImportFehler, match="480"):
        importe.starten(conn, 1, "mock", 481)


# ---------- Auto-Import ----------

def test_auto_setzen(conn):
    assert importe.auto_holen(conn, 1) == {"google": None, "bing": None}
    assert importe.auto_setzen(conn, 1, "mock") == {"google": "mock", "bing": None}
    assert importe.auto_setzen(conn, 1, "bing_mock") == {"google": "mock", "bing": "bing_mock"}
    assert importe.auto_setzen(conn, 1, "gsc") == {"google": "gsc", "bing": "bing_mock"}  # ersetzt mock
    assert importe.auto_setzen(conn, 1, None, "google") == {"google": None, "bing": "bing_mock"}
    with pytest.raises(importe.ImportFehler):
        importe.auto_setzen(conn, 1, "quatsch")
    with pytest.raises(importe.ImportFehler, match="Suchmaschine angeben"):
        importe.auto_setzen(conn, 1, None)
    with pytest.raises(importe.ImportFehler, match="gehört nicht"):
        importe.auto_setzen(conn, 1, "bing", "google")


def test_faellig_erster_import_und_nachholen(conn):
    assert importe.faellig(conn, HEUTE) == []  # Auto aus
    importe.auto_setzen(conn, 1, "mock")
    assert importe.faellig(conn, HEUTE) == [{"projekt_id": 1, "quelle": "mock", "von": "2026-07-10",
                                             "bis": "2026-10-07"}]  # erstes Mal 90 Tage
    # Daten bis 2026-10-02 vorhanden → ab 2 Tage davor nachholen
    importe.starten(conn, 1, "mock", 3, bis=date(2026, 10, 2), warten=True)
    assert importe.faellig(conn, HEUTE)[0]["von"] == "2026-09-30"


def test_auto_lauf_und_danach_nichts_faellig(conn):
    importe.auto_setzen(conn, 1, "mock")
    importe.starten(conn, 1, "mock", 3, bis=date(2026, 10, 4), warten=True)
    gelaufen = importe.auto_lauf(conn, HEUTE)
    assert [(i["ausloeser"], i["status"], i["von"], i["bis"]) for i in gelaufen] == \
        [("auto", "fertig", "2026-10-02", "2026-10-07")]
    assert importe.faellig(conn, HEUTE) == []


def test_nach_fehler_pause(conn, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GSC_SCHLUESSEL", tmp_path / "fehlt.json")
    importe.auto_setzen(conn, 1, "gsc")
    assert importe.auto_lauf(conn, HEUTE)[0]["status"] == "fehler"
    assert importe.faellig(conn, HEUTE) == []  # kein Dauerfeuer bei fehlendem Zugang
    conn.execute("UPDATE gsc_importe SET gestartet_am = datetime('now', '-7 hours')")
    conn.commit()
    assert len(importe.faellig(conn, HEUTE)) == 1


# ---------- REST und UI ----------

def test_api_und_ui():
    from app.web import app
    client = TestClient(app)
    p = client.post("/api/projekte", json={"domain": "ex.de"}).json()["id"]
    r = client.post(f"/projekte/{p}/positionen/import", data={"quelle": "mock", "tage": "10"})
    assert r.status_code == 200 and "import-status" in r.text
    ende = time.time() + 10
    while "HX-Refresh" not in (a := client.get(f"/projekte/{p}/positionen/import-status")).headers:
        assert time.time() < ende
        time.sleep(0.05)
    assert "Letzter Import" in a.text and "Testdaten" in a.text
    assert client.get(f"/api/projekte/{p}/positionen/importe").json()[0]["status"] == "fertig"
    antwort = client.post(f"/projekte/{p}/positionen/auto", data={"quelle": "mock", "suchmaschine": "google"}).text
    assert "Google: Testdaten" in antwort and "Bing: aus" in antwort
    assert client.get(f"/api/projekte/{p}/positionen/auto").json() == {"google": "mock", "bing": None}
    assert client.put(f"/api/projekte/{p}/positionen/auto", json={"quelle": None, "suchmaschine": "google"}
                      ).json() == {"google": None, "bing": None}
    assert client.put(f"/api/projekte/{p}/positionen/auto", json={"quelle": "x"}).status_code == 400
    assert "Täglich automatisch" in client.get(f"/projekte/{p}/positionen").text
