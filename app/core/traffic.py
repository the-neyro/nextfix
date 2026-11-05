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


def fuer_urls(daten: dict, urls) -> tuple[int | None, int | None, str]:
    """Importierte Klicks und Impressionen und Abdeckung der genannten URLs."""
    schluesselmenge = {schluessel(u) for u in urls}
    gefunden = [daten["seiten"][s] for s in schluesselmenge if s in daten["seiten"]]
    if not gefunden:
        return None, None, "keine"
    status = "passend" if len(gefunden) == len(schluesselmenge) else "teilweise"
    return sum(k for k, _ in gefunden), sum(i for _, i in gefunden), status


def _zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def text(klicks: int | None, impressionen: int | None, tage: int, status: str = "passend") -> str:
    """Zeile für die Aufgabe. Fehlende Zuordnungen sind keine Nullmessung."""
    if klicks is None or impressionen is None:
        return "Keine passenden Google-Daten für die betroffenen Seiten"
    if impressionen == 0:
        zeile = f"Keine Impressionen bei Google in {tage} Tagen (importierte Daten)"
    else:
        k = "1 Klick" if klicks == 1 else f"{_zahl(klicks)} Klicks"
        zeile = f"{k}, {_zahl(impressionen)} Impressionen bei Google in {tage} Tagen"
    if status == "teilweise":
        zeile += " · Google-Daten für einen Teil der betroffenen Seiten"
    return zeile
