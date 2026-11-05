"""Nur erneut erhobene Befunde können beim Crawl-Vergleich als behoben gelten."""

import asyncio
import json

import pytest

from app import checks
from app.core import aufgaben, projekte, vergleich
from app.db import verbinden

START = "https://vergleich.example/"
URL = START + "artikel"


def _crawl(conn, projekt_id):
    return conn.execute("INSERT INTO crawls (projekt_id, start_url, status) VALUES (?, ?, 'fertig')",
                        (projekt_id, START)).lastrowid


def _seite(conn, crawl_id, url=URL, **werte):
    felder = {"status_code": 200, "woerter": 100, "title": "Ein neuer Titel", **werte}
    return conn.execute(f"INSERT INTO seiten (crawl_id, url, tiefe, {', '.join(felder)}) "
                        f"VALUES (?, ?, 1, {', '.join('?' for _ in felder)})",
                        (crawl_id, url, *felder.values())).lastrowid


def _fund(conn, crawl_id, check_id, seite_id=None):
    conn.execute("INSERT INTO issues (crawl_id, check_id, seite_id) VALUES (?, ?, ?)",
                 (crawl_id, check_id, seite_id))


@pytest.fixture
def wiederholung():
    conn = verbinden()
    projekt_id = projekte.anlegen(conn, "vergleich.example").id
    vorher = _crawl(conn, projekt_id)
    return conn, projekt_id, vorher, _crawl(conn, projekt_id)


@pytest.mark.parametrize(("seite", "einstellungen"), [
    (None, {}),
    ({"status_code": None, "blockiert": 1, "woerter": None}, {}),
    ({"status_code": None, "abruf_fehler": "Timeout", "woerter": None}, {}),
    ({"status_code": 503, "woerter": None}, {}),
    ({"woerter": None}, {}),
    ({"x_robots_tag": "noindex"}, {}),
    ({"meta_robots": "noindex"}, {}),
    ({"render_fehler": "Browser-Timeout"}, {"js_rendern": 1}),
    ({"js_app": "app"}, {}),
    ({}, {"checks_aus": "title_fehlt"}),
    ({}, {"status": "abgebrochen"}),
])
def test_inhalt_ohne_wiederholte_messung_bleibt_offen(wiederholung, seite, einstellungen):
    conn, _, vorher, jetzt = wiederholung
    _fund(conn, vorher, "title_fehlt", _seite(conn, vorher, title=None))
    if seite is not None:
        _seite(conn, jetzt, **seite)
    for feld, wert in einstellungen.items():
        conn.execute(f"UPDATE crawls SET {feld}=? WHERE id=?", (wert, jetzt))

    ergebnis = vergleich.treffer_vergleich(conn, jetzt, "title_fehlt")
    assert ergebnis["behoben"] == []
    assert ergebnis["nicht_nachgeprueft"] == [URL]
    a = aufgaben.liste(conn, jetzt)
    assert a["erledigt"] == []
    assert [offen["id"] for offen in a["nicht_nachgeprueft"]] == ["title_fehlt"]


def test_wirklich_reparierter_titel_gilt_als_behoben(wiederholung):
    conn, _, vorher, jetzt = wiederholung
    alte_seite = _seite(conn, vorher, title=None)
    _fund(conn, vorher, "title_fehlt", alte_seite)
    _seite(conn, jetzt)
    checks.ausfuehren(conn, jetzt)

    assert vergleich.treffer_vergleich(conn, jetzt, "title_fehlt")["behoben"] == [URL]
    a = aufgaben.liste(conn, jetzt)
    assert [erledigt["id"] for erledigt in a["erledigt"]] == ["title_fehlt"]
    assert a["nicht_nachgeprueft"] == []


def test_geaenderter_renderingmodus_bestaetigt_keinen_inhaltsfix(wiederholung):
    conn, _, vorher, jetzt = wiederholung
    conn.execute("UPDATE crawls SET js_rendern=1 WHERE id=?", (vorher,))
    _fund(conn, vorher, "title_fehlt", _seite(conn, vorher, title=None, woerter_roh=0))
    _seite(conn, jetzt)
    assert vergleich.treffer_vergleich(conn, jetzt, "title_fehlt")["nicht_nachgeprueft"] == [URL]


def test_website_ohne_messung_bleibt_offen(wiederholung):
    conn, _, vorher, jetzt = wiederholung
    _fund(conn, vorher, "http_nicht_auf_https")
    _fund(conn, vorher, "robots_formatfehler")
    _fund(conn, vorher, "sitemap_fehlt")
    facts = {"http_zu_https": {"ok": True, "fehler": "Timeout"}}
    conn.execute("UPDATE crawls SET fakten=?, sitemap_status=200 WHERE id=?", (json.dumps(facts), jetzt))
    conn.execute("INSERT INTO sitemap_dateien (crawl_id, url, status, fehler) VALUES (?, ?, 200, 'XML')",
                 (jetzt, START + "sitemap.xml"))

    aenderungen = {a["id"]: a["status"] for a in vergleich.vergleich(conn, jetzt)["aenderungen"]}
    assert aenderungen == dict.fromkeys(("http_nicht_auf_https", "robots_formatfehler", "sitemap_fehlt"),
                                       "nicht_nachgeprueft")
    assert vergleich.treffer_vergleich(conn, jetzt, "robots_formatfehler")["nicht_nachgeprueft"] == [None]
    assert aufgaben.liste(conn, jetzt)["erledigt"] == []

    conn.execute("UPDATE crawls SET robots_status=200, robots_text='User-agent: *' WHERE id=?", (jetzt,))
    facts["http_zu_https"] = {"ok": True, "status": 200}
    conn.execute("UPDATE crawls SET fakten=? WHERE id=?", (json.dumps(facts), jetzt))
    conn.execute("UPDATE sitemap_dateien SET fehler=NULL WHERE crawl_id=?", (jetzt,))
    assert all(a["status"] == "behoben" for a in vergleich.vergleich(conn, jetzt)["aenderungen"])


def test_duplikat_ohne_zweite_seite_bleibt_offen(wiederholung):
    conn, _, vorher, jetzt = wiederholung
    partner = START + "partner"
    _fund(conn, vorher, "title_doppelt", _seite(conn, vorher))
    _fund(conn, vorher, "title_doppelt", _seite(conn, vorher, partner))
    _seite(conn, jetzt)
    checks.ausfuehren(conn, jetzt)
    assert vergleich.treffer_vergleich(conn, jetzt, "title_doppelt")["nicht_nachgeprueft"] == [URL, partner]

    _seite(conn, jetzt, partner, title="Anderer Titel")
    checks.ausfuehren(conn, jetzt)
    assert vergleich.treffer_vergleich(conn, jetzt, "title_doppelt")["behoben"] == [URL, partner]


def test_defektes_bild_ohne_status_bleibt_offen(wiederholung):
    conn, _, vorher, jetzt = wiederholung
    bild = START + "bild.jpg"
    _fund(conn, vorher, "interne_bilder_defekt", _seite(conn, vorher))
    seite_id = _seite(conn, jetzt)
    conn.execute("INSERT INTO links (crawl_id, seite_id, ziel_url, art, intern) VALUES (?, ?, ?, 'img', 1)",
                 (jetzt, seite_id, bild))
    checks.ausfuehren(conn, jetzt)
    assert vergleich.treffer_vergleich(conn, jetzt, "interne_bilder_defekt")["nicht_nachgeprueft"] == [URL]

    conn.execute("INSERT INTO ressourcen (crawl_id, url, art, status_code) VALUES (?, ?, 'img', 200)", (jetzt, bild))
    checks.ausfuehren(conn, jetzt)
    assert vergleich.treffer_vergleich(conn, jetzt, "interne_bilder_defekt")["behoben"] == [URL]


def test_vitals_brauchen_den_messwert_fuer_dieselbe_url(wiederholung):
    conn, _, vorher, jetzt = wiederholung
    _fund(conn, vorher, "ladezeit_lcp", _seite(conn, vorher))
    _seite(conn, jetzt)
    lauf = conn.execute("INSERT INTO vitals_laeufe (crawl_id, status, gesamt) VALUES (?, 'fertig', 1)",
                        (jetzt,)).lastrowid
    conn.execute("INSERT INTO vitals (lauf_id, url, geraet, cls) VALUES (?, ?, 'mobile', 0)", (lauf, URL))

    assert vergleich.treffer_vergleich(conn, jetzt, "ladezeit_lcp")["nicht_nachgeprueft"] == [URL]
    conn.execute("UPDATE vitals SET lcp=1500 WHERE lauf_id=? AND url=?", (lauf, URL))
    assert vergleich.treffer_vergleich(conn, jetzt, "ladezeit_lcp")["behoben"] == [URL]


@pytest.mark.parametrize(("status", "auswertung", "meldung"), [
    ("fertig", "keine_seiten", "Keine auswertbaren HTML-Seiten"),
    ("abgebrochen", "abgebrochen", "Prüfung abgebrochen"),
])
def test_leere_oder_abgebrochene_pruefung_ueber_ui_rest_und_mcp(wiederholung, status, auswertung, meldung):
    from fastapi.testclient import TestClient

    from app.mcp_server import server
    from app.web import app

    conn, projekt_id, vorher, jetzt = wiederholung
    _fund(conn, vorher, "title_fehlt", _seite(conn, vorher, title=None))
    conn.execute("UPDATE crawls SET health=70 WHERE id=?", (vorher,))
    conn.execute("UPDATE crawls SET status=? WHERE id=?", (status, jetzt))
    conn.commit()

    client = TestClient(app)
    uebersicht = client.get(f"/projekte/{projekt_id}")
    assert uebersicht.status_code == 200 and meldung in uebersicht.text
    assert "Seit der letzten Prüfung nicht nachgeprüft" in uebersicht.text
    assert "Alles erledigt" not in uebersicht.text

    api = client.get(f"/api/crawls/{jetzt}/aufgaben").json()
    assert api["auswertung"] == auswertung
    assert api["nicht_nachgeprueft"][0]["id"] == "title_fehlt"
    assert api["erledigt"] == []
    assert client.get(f"/api/crawls/{jetzt}/vergleich/title_fehlt").json()["nicht_nachgeprueft"] == [URL]
    assert "Nicht nachgeprüft" in client.get(f"/crawls/{jetzt}/vergleich/title_fehlt").text
    mcp = asyncio.run(server.call_tool("treffer_vergleich", {"crawl_id": jetzt, "check_id": "title_fehlt"}))
    assert "nicht_nachgeprueft" in str(mcp) and URL in str(mcp)
