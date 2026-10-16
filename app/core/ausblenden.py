"""„Bewusst so“: Probleme oder Seiten ausblenden, die absichtlich so bleiben (z. B. Login-Seite ohne Text).

Ausgeblendetes zählt nicht mehr in Website-Zustand, Teilnoten und „Was jetzt tun“. Es gilt fürs ganze Projekt,
also auch für ältere und künftige Crawls, und lässt sich jederzeit rückgängig machen. Gespeicherte Zustandswerte
der Crawls werden dabei neu berechnet, damit der Verlauf zusammenpasst.
"""

import sqlite3

from app import checks
from app.core import projekte


class AusblendenFehler(ValueError):
    """Ungültige Eingabe."""


# Bedingung für Abfragen auf issues i LEFT JOIN seiten s: nur Treffer, die nicht ausgeblendet sind.
NICHT_AUSGEBLENDET = """NOT EXISTS (
    SELECT 1 FROM ausblendungen a JOIN crawls k ON k.projekt_id = a.projekt_id
    WHERE k.id = i.crawl_id AND (a.check_id IS NULL OR a.check_id = i.check_id)
      AND (a.url IS NULL OR a.url = s.url))"""


def ausblenden(conn: sqlite3.Connection, projekt_id: int, check_id: str | None = None, url: str | None = None,
               grund: str = "") -> dict:
    """Problem (check_id), Seite (url) oder ein Problem auf einer Seite (beides) ausblenden."""
    projekte.holen(conn, projekt_id)
    check_id, url = check_id or None, url or None
    if check_id is None and url is None:
        raise AusblendenFehler("check_id oder url angeben")
    if check_id is not None and check_id not in checks.REGISTER:
        raise AusblendenFehler(f"Unbekannter Check: {check_id}")
    vorhanden = conn.execute("SELECT id FROM ausblendungen WHERE projekt_id=? AND check_id IS ? AND url IS ?",
                             (projekt_id, check_id, url)).fetchone()
    if vorhanden:
        conn.execute("UPDATE ausblendungen SET grund=? WHERE id=?", (grund.strip(), vorhanden[0]))
        neue_id = vorhanden[0]
    else:
        neue_id = conn.execute("INSERT INTO ausblendungen (projekt_id, check_id, url, grund) VALUES (?, ?, ?, ?)",
                               (projekt_id, check_id, url, grund.strip())).lastrowid
    conn.commit()
    neu_bewerten(conn, projekt_id)
    return _holen(conn, neue_id)


def einblenden(conn: sqlite3.Connection, projekt_id: int, ausblendung_id: int) -> None:
    """Ausblendung zurücknehmen."""
    if conn.execute("DELETE FROM ausblendungen WHERE id=? AND projekt_id=?",
                    (ausblendung_id, projekt_id)).rowcount == 0:
        raise AusblendenFehler(f"Ausblendung {ausblendung_id} nicht gefunden")
    conn.commit()
    neu_bewerten(conn, projekt_id)


def liste(conn: sqlite3.Connection, projekt_id: int) -> list[dict]:
    projekte.holen(conn, projekt_id)
    ids = conn.execute("SELECT id FROM ausblendungen WHERE projekt_id=? ORDER BY check_id, url",
                       (projekt_id,)).fetchall()
    return [_holen(conn, z[0]) for z in ids]


def regeln(conn: sqlite3.Connection, crawl_id: int) -> list[tuple[int, str | None, str | None]]:
    """(id, check_id, url) aller Ausblendungen des Projekts, zu dem der Crawl gehört."""
    return [tuple(z) for z in conn.execute("""SELECT a.id, a.check_id, a.url FROM ausblendungen a
        JOIN crawls k ON k.projekt_id = a.projekt_id WHERE k.id=? ORDER BY a.id""", (crawl_id,))]


def trifft(regeln_: list[tuple], check_id: str | None, url: str | None) -> int | None:
    """Id der Ausblendung, die den Treffer (check_id, url) verdeckt, sonst None. url None = ganze Website."""
    return next((i for i, c, u in regeln_ if (c is None or c == check_id) and (u is None or u == url)), None)


def genau(regeln_: list[tuple], check_id: str | None, url: str | None) -> int | None:
    """Id der Ausblendung genau für (check_id, url), sonst None."""
    return next((i for i, c, u in regeln_ if c == check_id and u == url), None)


def neu_bewerten(conn: sqlite3.Connection, projekt_id: int) -> None:
    """Gespeicherten Zustand aller abgeschlossenen Crawls neu berechnen."""
    from app.core import audit   # zirkulären Import vermeiden

    for (crawl_id,) in conn.execute("SELECT id FROM crawls WHERE projekt_id=? AND status IN ('fertig', 'abgebrochen')",
                                    (projekt_id,)).fetchall():
        conn.execute("UPDATE crawls SET health=? WHERE id=?", (audit._health(conn, crawl_id), crawl_id))
    conn.commit()


def _holen(conn: sqlite3.Connection, ausblendung_id: int) -> dict:
    z = dict(conn.execute("SELECT * FROM ausblendungen WHERE id=?", (ausblendung_id,)).fetchone())
    c = checks.REGISTER.get(z["check_id"]) if z["check_id"] else None
    z["check_name"] = c.name if c else None
    z["art"] = "problem" if z["url"] is None else "seite" if z["check_id"] is None else "fundstelle"
    return z
