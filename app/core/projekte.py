"""Service: Projekte (eine Website = ein Projekt)."""

import sqlite3
from dataclasses import asdict, dataclass
from urllib.parse import urlparse


class ProjektFehler(ValueError):
    """Ungültige Eingabe oder Konflikt beim Projekt."""


@dataclass
class Projekt:
    id: int
    name: str
    domain: str
    angelegt_am: str

    def als_dict(self) -> dict:
        return asdict(self)


def domain_normalisieren(eingabe: str) -> str:
    """'https://WWW.Example.de/pfad' -> 'www.example.de'."""
    text = eingabe.strip().lower()
    if not text:
        raise ProjektFehler("Domain fehlt")
    if "://" not in text:
        text = "http://" + text
    host = urlparse(text).hostname
    if not host or "." not in host:
        raise ProjektFehler(f"Ungültige Domain: {eingabe!r}")
    return host


def anlegen(conn: sqlite3.Connection, domain: str, name: str | None = None) -> Projekt:
    domain = domain_normalisieren(domain)
    name = (name or "").strip() or domain
    try:
        cur = conn.execute(
            "INSERT INTO projekte (name, domain) VALUES (?, ?)", (name, domain)
        )
    except sqlite3.IntegrityError:
        raise ProjektFehler(f"Projekt für {domain} existiert schon") from None
    conn.commit()
    return holen(conn, cur.lastrowid)


def holen(conn: sqlite3.Connection, projekt_id: int) -> Projekt:
    zeile = conn.execute("SELECT * FROM projekte WHERE id = ?", (projekt_id,)).fetchone()
    if zeile is None:
        raise ProjektFehler(f"Projekt {projekt_id} nicht gefunden")
    return Projekt(**dict(zeile))


def liste(conn: sqlite3.Connection) -> list[Projekt]:
    zeilen = conn.execute("SELECT * FROM projekte ORDER BY id").fetchall()
    return [Projekt(**dict(z)) for z in zeilen]


def loeschen(conn: sqlite3.Connection, projekt_id: int) -> None:
    holen(conn, projekt_id)
    conn.execute("DELETE FROM projekte WHERE id = ?", (projekt_id,))
    conn.commit()
