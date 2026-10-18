"""Aufgaben-Priorität mit Search-Console-Daten: Klicks ordnen innerhalb derselben Wirkungsstufe."""

from datetime import date, timedelta

import pytest

from app.core import audit, aufgaben, projekte, traffic
from app.db import verbinden


@pytest.fixture
def crawl(testseite):
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0)
    return conn, p.id, audit.crawl_starten(conn, p.id, warten=True)["id"]


def _gsc(conn, projekt_id, seite, klicks, impressionen, datum="2026-10-15", query="radweg", quelle="gsc"):
    conn.execute("INSERT INTO gsc_zeilen (projekt_id, datum, query, seite, land, geraet, klicks, impressionen,"
                 " position, quelle) VALUES (?,?,?,?, 'deu', 'MOBILE', ?,?, 3.0, ?)",
                 (projekt_id, datum, query, seite, klicks, impressionen, quelle))
    conn.commit()


def _urls(conn, crawl_id, check_id) -> list[str]:
    return [t["url"] for t in audit.issue_details(conn, crawl_id, check_id)["treffer"]]


def test_schluessel_ohne_schema_und_www():
    assert traffic.schluessel("https://www.Ex.de/a?b=1") == traffic.schluessel("http://ex.de/a?b=1") == "ex.de/a?b=1"
    assert traffic.schluessel("https://ex.de") == "ex.de/"
    assert traffic.schluessel("https://ex.de/a") != traffic.schluessel("https://ex.de/a/")


def test_zeitraum_28_tage_bis_zum_neuesten_datum():
    conn = verbinden()
    p = projekte.anlegen(conn, "ex.de").id
    assert traffic.pro_seite(conn, p) is None
    bis = date(2026, 10, 15)
    _gsc(conn, p, "https://ex.de/a", 5, 50, bis.isoformat())
    _gsc(conn, p, "https://www.ex.de/a", 1, 10, (bis - timedelta(days=27)).isoformat(), query="b")
    _gsc(conn, p, "https://ex.de/a", 100, 1000, (bis - timedelta(days=28)).isoformat(), query="c")   # zu alt
    _gsc(conn, p, "https://ex.de/a", 70, 700, bis.isoformat(), query="d", quelle="bing")              # nie mischen
    d = traffic.pro_seite(conn, p)
    assert (d["von"], d["bis"]) == ("2026-09-18", "2026-10-15")
    assert d["seiten"] == {"ex.de/a": (6, 60)} and d["summe"] == (6, 60)
    assert traffic.fuer_urls(d, ["http://ex.de/a", "https://www.ex.de/a", "https://ex.de/fehlt"]) == (6, 60)


def test_text():
    assert traffic.text(1340, 12400, 28) == "1.340 Klicks, 12.400 Impressionen bei Google in 28 Tagen"
    assert traffic.text(1, 3, 28).startswith("1 Klick,")
    assert traffic.text(0, 0, 28) == "Keine Impressionen bei Google in 28 Tagen"


def test_ohne_gsc_bleibt_reihenfolge(crawl):
    conn, _, c = crawl
    liste = aufgaben.liste(conn, c)
    assert liste["suchdaten"] is None
    assert all(a["klicks"] is None and a["traffic_text"] is None for a in liste["aufgaben"])
    alt = sorted(liste["aufgaben"], key=lambda a: (-a["gewinn"], a["aufwand"], -a["seiten"]))
    assert [a["id"] for a in liste["aufgaben"]] == [a["id"] for a in alt]


def test_klicks_ordnen_innerhalb_der_stufe(crawl, testseite):
    conn, p, c = crawl
    vorher = aufgaben.liste(conn, c)["aufgaben"]
    stufen = {}
    for a in vorher:
        if not a["ganze_site"]:
            stufen.setdefault(a["wirkung"], []).append(a)
    wirkung, gruppe = next((w, g) for w, g in stufen.items() if len(g) >= 2)
    letzte = gruppe[-1]
    # Search Console meldet https://www. – der Crawl lief über http:// ohne www.
    for url in _urls(conn, c, letzte["id"]):
        _gsc(conn, p, url.replace("http://", "https://www."), 40, 900)

    nachher = aufgaben.liste(conn, c)
    assert nachher["suchdaten"]["tage"] == 28
    neu = [a for a in nachher["aufgaben"] if a["wirkung"] == wirkung]
    gehoben = next(a for a in neu if a["id"] == letzte["id"])
    assert gehoben["klicks"] >= 40 and "Klicks" in gehoben["traffic_text"]
    assert neu.index(gehoben) < len(neu) - 1   # vorher Letzte ihrer Stufe, jetzt nicht mehr
    assert [a["klicks"] for a in neu] == sorted((a["klicks"] for a in neu), reverse=True)
    # Stufen bleiben in ihrer Reihenfolge: Traffic hebt keine Warnung über einen Fehler mit höherer Wirkung
    rang = [aufgaben.WIRKUNG_RANG[a["wirkung"]] for a in nachher["aufgaben"]]
    assert rang == sorted(rang)
    # Ganze Website: alle Klicks des Zeitraums
    summe = traffic.pro_seite(conn, p)["summe"]
    assert all((a["klicks"], a["impressionen"]) == summe for a in nachher["aufgaben"] if a["ganze_site"])


def test_oberflaeche_zeigt_traffic(crawl):
    from fastapi.testclient import TestClient
    from app.web import app
    conn, p, c = crawl
    url = _urls(conn, c, aufgaben.liste(conn, c)["aufgaben"][0]["id"])
    _gsc(conn, p, (url or ["http://127.0.0.1/"])[0], 7, 123, quelle="mock")
    seite = TestClient(app).get(f"/projekte/{p}").text
    assert "bei gleicher Wirkung nach Klicks bei Google" in seite and "Beispieldaten" in seite
    assert "Impressionen bei Google in 28 Tagen" in seite
