"""Service: Domain-Autorität (Open PageRank) für Projekte – abrufen, zwischenspeichern, vergleichen.

Ein Wert 0–10 je Domain, wie stark andere Websites auf sie verlinken (logarithmisch: 3 → 4 ist ein viel größerer
Schritt als 1 → 2). Kleine lokale Websites liegen meist bei 1–3, das ist normal. Deshalb ohne Ampelfarben anzeigen
und vor allem mit Mitbewerbern vergleichen.

Abruf nach jedem Crawl, per Knopf und per MCP. Gespeichert wird je Domain; neu abgefragt erst nach MAX_ALTER_TAGE,
weil die Daten nur etwa monatlich neu berechnet werden (schont das Kontingent).
"""

import ipaddress
import sqlite3

from app import config
from app.core import projekte
from app.linkdaten import openpagerank as opr

MAX_ALTER_TAGE = 30


def verfuegbar() -> bool:
    return config.OPR_SCHLUESSEL.is_file()


def domain_normal(domain: str) -> str | None:
    """'www.Beispiel.de' → 'beispiel.de'; None für IP-Adressen und localhost (gibt es bei Open PageRank nicht)."""
    d = domain.strip().lower().split(":")[0].removeprefix("www.")
    try:
        ipaddress.ip_address(d)
        return None
    except ValueError:
        return None if d in ("localhost", "") or "." not in d else d


def werte(conn: sqlite3.Connection, domains: list[str]) -> dict[str, dict]:
    """Gespeicherte Werte (ohne Abruf). Schlüssel: Domain wie übergeben."""
    ergebnis = {}
    for d in domains:
        n = domain_normal(d)
        z = conn.execute("SELECT * FROM autoritaet WHERE domain=?", (n,)).fetchone() if n else None
        if z:
            ergebnis[d] = dict(z)
    return ergebnis


def aktualisieren(conn: sqlite3.Connection, domains: list[str], neu: bool = False, client=None) -> dict[str, dict]:
    """Fehlende oder veraltete Werte bei Open PageRank abfragen, dann alle gespeicherten Werte liefern."""
    normal = {n for n in map(domain_normal, domains) if n}
    if not neu:
        frisch = {z[0] for z in conn.execute(
            f"SELECT domain FROM autoritaet WHERE julianday('now') - julianday(abgerufen_am) < {MAX_ALTER_TAGE}"
            f" AND domain IN ({','.join('?' * len(normal))})", tuple(normal))} if normal else set()
        normal -= frisch
    if normal:
        for domain, w in opr.abfragen(sorted(normal), client=client).items():
            conn.execute("INSERT OR REPLACE INTO autoritaet (domain, wert, rang, stand, fehler, abgerufen_am)"
                         " VALUES (?, ?, ?, ?, ?, datetime('now'))",
                         (domain, w["wert"], w["rang"], w["stand"], w["fehler"]))
        conn.commit()
    return werte(conn, domains)


def still_aktualisieren(conn: sqlite3.Connection, domains: list[str]) -> None:
    """Nach dem Crawl: nur wenn ein Schlüssel da ist, Fehler (offline, Kontingent) ignorieren."""
    if not verfuegbar():
        return
    try:
        aktualisieren(conn, domains)
    except opr.OprFehler:
        pass


def vergleich(conn: sqlite3.Connection) -> list[dict]:
    """Alle Projekte mit ihrem gespeicherten Wert, stärkste zuerst (Projekte ohne Wert am Ende)."""
    ps = projekte.liste(conn)
    w = werte(conn, [p.domain for p in ps])
    zeilen = [{"projekt_id": p.id, "name": p.name, "domain": p.domain,
               "wert": w.get(p.domain, {}).get("wert"), "rang": w.get(p.domain, {}).get("rang")} for p in ps]
    return sorted(zeilen, key=lambda z: (z["wert"] is None, -(z["wert"] or 0)))
