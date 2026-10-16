"""Service: Zugang zu den Datenquellen je Projekt (Property wählen, Status, Verbindung testen).

quelle: gsc (Google Search Console, Service-Account-Schlüssel) oder bing (Bing Webmaster, API-Schlüssel).
Der Schlüssel gilt für alle Projekte (config.GSC_SCHLUESSEL / config.BING_SCHLUESSEL).
Pro Projekt und Quelle wird nur die Property gespeichert; ohne Eintrag wird sie beim ersten
Import automatisch gesucht und dann gemerkt.
"""

import sqlite3

from app import config, gsc
from app.core import projekte
from app.gsc import api, bing

NAMEN = {"gsc": "Search Console", "bing": "Bing Webmaster Tools"}


def _quelle_pruefen(quelle: str) -> None:
    if quelle not in gsc.MIT_ZUGANG:
        raise gsc.GscFehler(f"Unbekannte Quelle: {quelle} ({' | '.join(gsc.MIT_ZUGANG)})")


def property_holen(conn: sqlite3.Connection, projekt_id: int, quelle: str = "gsc") -> str | None:
    z = conn.execute("SELECT property FROM quelle_properties WHERE projekt_id = ? AND quelle = ?",
                     (projekt_id, quelle)).fetchone()
    return z["property"] if z else None


def property_setzen(conn: sqlite3.Connection, projekt_id: int, prop: str | None, quelle: str = "gsc") -> str | None:
    """Property festlegen. Leer = automatisch suchen.
    gsc: sc-domain:example.de oder https://www.example.de/ · bing: https://www.example.de/"""
    projekte.holen(conn, projekt_id)
    _quelle_pruefen(quelle)
    prop = (prop or "").strip()
    if not prop:
        conn.execute("DELETE FROM quelle_properties WHERE projekt_id = ? AND quelle = ?", (projekt_id, quelle))
        conn.commit()
        return None
    if prop.startswith(("http://", "https://")):
        prop = prop if prop.endswith("/") else prop + "/"  # URL-Properties enden immer mit /
    elif quelle == "bing":
        raise gsc.GscFehler("Bing-Website muss mit http(s):// beginnen")
    elif not (prop.startswith("sc-domain:") and "." in prop):
        raise gsc.GscFehler("Property muss mit sc-domain: oder http(s):// beginnen")
    conn.execute("INSERT OR REPLACE INTO quelle_properties (projekt_id, quelle, property) VALUES (?, ?, ?)",
                 (projekt_id, quelle, prop))
    conn.commit()
    return prop


def property_ermitteln(conn: sqlite3.Connection, projekt_id: int, quelle) -> str:
    """Gespeicherte Property oder passende suchen und merken. quelle: Quellen-Objekt (gsc oder bing)."""
    prop = property_holen(conn, projekt_id, quelle.name)
    if prop:
        return prop
    prop = quelle.property_finden(projekte.holen(conn, projekt_id).domain)
    return property_setzen(conn, projekt_id, prop, quelle.name)


def status(conn: sqlite3.Connection, projekt_id: int, quelle: str = "gsc") -> dict:
    """Ist ein Schlüssel da, welche Property gilt? Bei gsc auch die Service-Account-Adresse,
    die in der Search Console freigegeben werden muss. Fragt nicht bei Google/Bing an."""
    projekte.holen(conn, projekt_id)
    _quelle_pruefen(quelle)
    pfad = config.GSC_SCHLUESSEL if quelle == "gsc" else config.BING_SCHLUESSEL
    ergebnis = {"quelle": quelle, "name": NAMEN[quelle], "schluessel_pfad": str(pfad), "schluessel_da": False,
                "client_email": None, "fehler": None, "property": property_holen(conn, projekt_id, quelle)}
    try:
        if quelle == "gsc":
            ergebnis["client_email"] = api.schluessel_laden()["client_email"]
        else:
            bing.schluessel_laden()  # nur prüfen, der Schlüssel selbst wird nie zurückgegeben
        ergebnis["schluessel_da"] = True
    except gsc.GscFehler as e:
        ergebnis["fehler"] = str(e)
    return ergebnis


def verbindung_testen(conn: sqlite3.Connection, projekt_id: int, quelle: str = "gsc") -> dict:
    """Meldet sich an und listet die freigegebenen Properties samt passender für dieses Projekt."""
    projekt = projekte.holen(conn, projekt_id)
    _quelle_pruefen(quelle)
    q = gsc.quelle_holen(quelle)
    ergebnis = {"quelle": quelle, "ok": False, "properties": [], "passend": None, "fehler": None}
    try:
        ergebnis["properties"] = q.properties()
        ergebnis["ok"] = True
        ergebnis["passend"] = property_holen(conn, projekt_id, quelle) or q.property_finden(projekt.domain)
    except gsc.GscFehler as e:
        ergebnis["fehler"] = str(e)
    return ergebnis
