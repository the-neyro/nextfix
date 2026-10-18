"""Suchtraffic je Seite aus der Google Search Console (Tabelle gsc_zeilen), kostenlos und lokal.

Wofür: Aufgaben, die Seiten mit Besuchern betreffen, kommen innerhalb derselben Wirkungsstufe zuerst – wie Semrush
und Ahrefs, die Schweregrad vorn lassen und Traffic als zweites Signal zeigen. Zeitraum: die letzten 28 Tage mit Daten
(die Search Console hinkt 2–3 Tage hinterher). Ohne Google-Daten liefert pro_seite None, dann bleibt alles wie gehabt.

Untergrenze: gsc_zeilen hat die Dimension Suchbegriff, anonymisierte Suchanfragen fehlen darin. Die Summe je Seite
liegt daher unter dem Wert, den die Search Console auf Seitenebene zeigt.
"""

import sqlite3
from datetime import date, timedelta
from urllib.parse import urlsplit

from app.core import positionen

TAGE = 28


def schluessel(url: str) -> str:
    """Vergleichbare Form: ohne Schema und www., Host klein. Die Search Console meldet https://www., der Crawl
    startet vielleicht bei http:// ohne www. – gemeint ist dieselbe Seite."""
    t = urlsplit(url)
    host = t.netloc.lower().removeprefix("www.")
    return f"{host}{t.path or '/'}" + (f"?{t.query}" if t.query else "")


def pro_seite(conn: sqlite3.Connection, projekt_id: int, tage: int = TAGE) -> dict | None:
    """{"von", "bis", "tage", "quellen", "seiten": {schluessel: (klicks, impressionen)}, "summe": (klicks, impr.)}"""
    bestand = positionen.bestand(conn, projekt_id, "google")
    if bestand is None:
        return None
    bis = date.fromisoformat(bestand["bis"])
    von = bis - timedelta(days=tage - 1)
    sql, werte = positionen._quellen_sql("google")
    seiten: dict[str, tuple[int, int]] = {}
    for url, klicks, impressionen in conn.execute(
            "SELECT seite, SUM(klicks), SUM(impressionen) FROM gsc_zeilen"
            f" WHERE projekt_id = ? AND datum BETWEEN ? AND ?{sql} GROUP BY seite",
            [projekt_id, von.isoformat(), bis.isoformat(), *werte]):
        k, i = seiten.get(schluessel(url), (0, 0))
        seiten[schluessel(url)] = (k + klicks, i + impressionen)
    summe = (sum(k for k, _ in seiten.values()), sum(i for _, i in seiten.values()))
    return {"von": von.isoformat(), "bis": bis.isoformat(), "tage": tage, "quellen": bestand["quellen"],
            "seiten": seiten, "summe": summe}


def fuer_urls(daten: dict, urls) -> tuple[int, int]:
    """Klicks und Impressionen der genannten Seiten (jede Seite einmal)."""
    gefunden = [daten["seiten"].get(s, (0, 0)) for s in {schluessel(u) for u in urls}]
    return sum(k for k, _ in gefunden), sum(i for _, i in gefunden)


def _zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def text(klicks: int, impressionen: int, tage: int) -> str:
    """Zeile für die Aufgabe, z. B. „340 Klicks, 12.400 Impressionen bei Google in 28 Tagen“."""
    if not impressionen:
        return f"Keine Impressionen bei Google in {tage} Tagen"
    k = "1 Klick" if klicks == 1 else f"{_zahl(klicks)} Klicks"
    return f"{k}, {_zahl(impressionen)} Impressionen bei Google in {tage} Tagen"
