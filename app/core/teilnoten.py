"""Teilnoten für die Projekt-Übersicht: Wo ist die Website schwach?

Der Website-Zustand (Health) bewertet nur, was die Prüfung sieht. Die Teilnoten zeigen daneben getrennt
Technik, Inhalt, KI-Suche, Ladezeit (Labor-Messung) und Sichtbarkeit bei Google (Search Console) –
jeweils 0–100, damit schwache Positionen nicht hinter guter Technik verschwinden.
"""

import sqlite3

from app.core import audit, autoritaet, positionen, projekte, vitals

TECHNIK = {"crawlbarkeit", "https", "technik", "performance", "international", "links"}


def liste(conn: sqlite3.Connection, projekt_id: int, crawl_id: int) -> list[dict]:
    """[{"name", "wert" (0–100 oder None), "hinweis", "link"}]"""
    noten = [
        {"name": "Technik", "wert": audit._health(conn, crawl_id, TECHNIK), "link": f"/crawls/{crawl_id}/issues"},
        {"name": "Inhalt", "wert": audit._health(conn, crawl_id, "inhalt"), "link": f"/crawls/{crawl_id}/themen/inhalt"},
        {"name": "KI-Suche", "wert": audit._health(conn, crawl_id, "ki"), "link": f"/crawls/{crawl_id}/themen/ki"},
    ]
    mobil = vitals.ergebnis(conn, crawl_id)["zusammenfassung"].get("mobile") or {}
    noten.append({"name": "Ladezeit mobil", "wert": mobil.get("score"), "link": f"/crawls/{crawl_id}/vitals",
                  "hinweis": None if mobil.get("score") is not None else "noch nicht gemessen"})
    noten.append(_sichtbarkeit(conn, projekt_id))
    noten.append(_autoritaet(conn, projekt_id))
    return noten


def _autoritaet(conn: sqlite3.Connection, projekt_id: int) -> dict:
    """Open PageRank 0–10, ohne Ampel (kleine Websites liegen normal bei 1–3), Vergleich in der Projektliste."""
    note = {"name": "Autorität", "wert": None, "skala": 10, "link": "/#autoritaet"}
    domain = projekte.holen(conn, projekt_id).domain
    w = autoritaet.werte(conn, [domain]).get(domain)
    if w and w["wert"] is not None:
        return {**note, "wert": w["wert"], "hinweis": "von 10 · Links anderer Websites"}
    if not autoritaet.verfuegbar():
        return {**note, "hinweis": "Open PageRank nicht verbunden"}
    return {**note, "hinweis": "noch keine Daten" if not w else "Domain dort unbekannt"}


def _sichtbarkeit(conn: sqlite3.Connection, projekt_id: int) -> dict:
    note = {"name": "Sichtbarkeit Google", "wert": None, "link": f"/projekte/{projekt_id}/positionen"}
    b = positionen.bestand(conn, projekt_id, "google")
    if not b:
        return {**note, "hinweis": "Search Console nicht verbunden"}
    k = positionen.uebersicht(conn, projekt_id, tage=28)["kennzahlen"]
    return {**note, "wert": k["sichtbarkeit"], "hinweis": "Testdaten" if "mock" in b["quellen"] else None}

