"""Register aller Checks. Ein Check = Metadaten + Funktion, die Treffer liefert.

Neue Checks: in einem Modul unter app/checks/ mit @check(...) dekorieren.
Die Funktion bekommt (conn, crawl_id) und liefert (seite_id | None, detail | None).
seite_id None = Problem betrifft die ganze Website.
"""

import json
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass

SCHWEREGRADE = ("error", "warning", "notice")

KATEGORIEN = {
    "crawlbarkeit": "Crawlbarkeit",
    "https": "HTTPS",
    "links": "Interne Verlinkung",
    "inhalt": "Inhalt & Meta",
    "performance": "Performance",
    "technik": "Technik & Markup",
    "international": "Internationales SEO",
    "ki": "KI-Suche",
}

Treffer = tuple[int | None, str | None]
CheckFunktion = Callable[[sqlite3.Connection, int], Iterable[Treffer]]


@dataclass(frozen=True)
class Check:
    id: str
    name: str
    schwere: str
    kategorie: str
    warum: str
    beheben: str
    funktion: CheckFunktion

    def als_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("id", "name", "schwere", "kategorie", "warum", "beheben")}


REGISTER: dict[str, Check] = {}


def check(id: str, name: str, schwere: str, kategorie: str, warum: str, beheben: str):
    assert schwere in SCHWEREGRADE, schwere
    assert kategorie in KATEGORIEN, kategorie

    def deko(funktion: CheckFunktion) -> CheckFunktion:
        if id in REGISTER:
            raise ValueError(f"Check-ID doppelt: {id}")
        REGISTER[id] = Check(id, name, schwere, kategorie, warum, beheben, funktion)
        return funktion

    return deko


# Bedingung für "HTML-Seite erfolgreich geparst"
HTML = "status_code = 200 AND woerter IS NOT NULL"


def fakten(conn: sqlite3.Connection, crawl_id: int) -> dict:
    """Site-weite Fakten des Crawls (siehe app/crawler/site.py)."""
    z = conn.execute("SELECT fakten FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    return json.loads(z[0]) if z and z[0] else {}


def json_spalte(conn: sqlite3.Connection, crawl_id: int, spalte: str, bedingung: str = "1") -> list[tuple[int, str, object]]:
    """(seite_id, url, geparste JSON-Spalte) für HTML-Seiten, bei denen die Spalte gefüllt ist."""
    zeilen = conn.execute(
        f"SELECT id, url, {spalte} FROM seiten WHERE crawl_id=? AND {HTML} AND {spalte} IS NOT NULL AND {bedingung}",
        (crawl_id,))
    return [(z[0], z[1], json.loads(z[2])) for z in zeilen]


def abfrage(conn: sqlite3.Connection, sql: str, *params) -> list[Treffer]:
    """Hilfe: SQL muss (seite_id, detail) liefern."""
    return [(z[0], None if z[1] is None else str(z[1])) for z in conn.execute(sql, params)]
