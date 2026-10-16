"""Checks: Katalog (katalog.py) + Module je Kategorie. Vorlage: docs/analyse/site-audit-checks.md."""

import sqlite3

# Module importieren, damit sich alle Checks im REGISTER eintragen
from app.checks import crawlbarkeit, duplikate, extern, inhalt, international, ki, ladezeit, links, ressourcen, site, sitemap, technik  # noqa: F401
from app.checks.katalog import KATEGORIEN, REGISTER, SCHWEREGRADE, Check


def ausfuehren(conn: sqlite3.Connection, crawl_id: int, ausgeschlossen: set[str] = frozenset()) -> int:
    """Alle Checks auf einen Crawl anwenden. Gibt die Anzahl gefundener Issues zurück."""
    conn.execute("DELETE FROM issues WHERE crawl_id=?", (crawl_id,))
    anzahl = 0
    for c in REGISTER.values():
        if c.id in ausgeschlossen:
            continue
        treffer = list(c.funktion(conn, crawl_id))
        conn.executemany(
            "INSERT INTO issues (crawl_id, check_id, seite_id, detail) VALUES (?,?,?,?)",
            [(crawl_id, c.id, seite_id, detail) for seite_id, detail in treffer],
        )
        anzahl += len(treffer)
    conn.commit()
    return anzahl


__all__ = ["KATEGORIEN", "REGISTER", "SCHWEREGRADE", "Check", "ausfuehren"]
