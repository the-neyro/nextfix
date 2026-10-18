"""SQLite-Zugriff: Verbindung öffnen und Schema anlegen."""

import sqlite3
import threading
from pathlib import Path

from collections.abc import Iterator

from app import config

SCHEMA = Path(__file__).with_name("schema.sql")

# Spalten, die nach dem ersten Schema dazugekommen sind: (tabelle, spalte, definition)
NACHTRAEGE = [
    ("crawls", "lebenszeichen", "TEXT"),
    ("crawls", "fakten", "TEXT"),
    ("crawls", "quelle", "TEXT NOT NULL DEFAULT 'website'"),
    ("einstellungen", "quelle", "TEXT NOT NULL DEFAULT 'website'"),
    ("seiten", "hreflang", "TEXT"),
    ("seiten", "markup", "TEXT"),
    ("seiten", "signatur", "TEXT"),
    ("seiten", "hat_passwort", "INTEGER"),
    ("seiten", "plugins", "TEXT"),
    ("seiten", "semantik", "TEXT"),
    ("seiten", "lesbarkeit", "TEXT"),
    ("seiten", "kaputte_links", "TEXT"),
    ("seiten", "last_modified", "TEXT"),
    ("ressourcen", "extern", "INTEGER NOT NULL DEFAULT 0"),
    ("ressourcen", "bytes", "INTEGER"),
    ("ressourcen", "content_encoding", "TEXT"),
    ("ressourcen", "gecacht", "INTEGER"),
    ("ressourcen", "minifiziert", "INTEGER"),
    ("einstellungen", "erlauben", "TEXT NOT NULL DEFAULT ''"),
    ("einstellungen", "sperren", "TEXT NOT NULL DEFAULT ''"),
    ("einstellungen", "parameter_entfernen", "TEXT NOT NULL DEFAULT ''"),
    ("einstellungen", "checks_aus", "TEXT NOT NULL DEFAULT ''"),
    ("crawls", "checks_aus", "TEXT NOT NULL DEFAULT ''"),
    ("einstellungen", "ladezeit_auto", "INTEGER NOT NULL DEFAULT 0"),
    ("einstellungen", "js_rendern", "INTEGER NOT NULL DEFAULT 0"),
    ("crawls", "js_rendern", "INTEGER NOT NULL DEFAULT 0"),
    ("seiten", "woerter_roh", "INTEGER"),
    ("seiten", "js_app", "TEXT"),
    ("seiten", "link_rank", "INTEGER"),
    ("seiten", "geo", "TEXT"),                          # JSON: Signale für KI-Suche (app/crawler/geo.py)
    ("seiten", "blockierend", "TEXT"),                  # JSON: render-blockierende Skripte im <head>
    ("seiten", "etag", "TEXT"),                         # HTTP-Header ETag
    ("seiten", "css_blockierend", "TEXT"),              # JSON: render-blockierende Stylesheets
    ("seiten", "bilder_ohne_masse", "INTEGER"),         # <img> ohne width/height
    ("ressourcen", "cache_sekunden", "INTEGER"),        # Cache-Dauer laut Header
    ("recherche_ideen", "volumen", "INTEGER"),          # Bing-Impressionen pro Monat (Ø der letzten Wochen)
    ("recherche_ideen", "volumen_quelle", "TEXT"),      # bing | bing_mock
    ("recherche_ideen", "trend", "TEXT"),               # JSON: Wochenwerte, älteste zuerst
    ("recherchen", "volumen_status", "TEXT"),           # NULL | laeuft | fertig | fehler
    ("recherchen", "volumen_fertig", "INTEGER NOT NULL DEFAULT 0"),
    ("recherchen", "volumen_gesamt", "INTEGER NOT NULL DEFAULT 0"),
    ("recherchen", "volumen_fehler", "TEXT"),
    ("recherchen", "volumen_lebenszeichen", "TEXT"),
]


# Datenbank-Dateien, deren Schema dieser Prozess schon angelegt hat (Pfad + Inode: eine neu angelegte Datei zählt neu)
_EINGERICHTET: set[tuple[str, int]] = set()
_EINRICHTEN = threading.Lock()


def verbinden(pfad: Path | str | None = None) -> sqlite3.Connection:
    """Öffnet die Datenbank und legt beim ersten Mal fehlende Tabellen an.

    Hintergrund-Jobs (Crawl, Suchvolumen) schreiben, während die Oberfläche alle paar hundert Millisekunden
    nachfragt. Damit sich das nicht gegenseitig sperrt: WAL-Modus (Lesen blockiert Schreiben nicht), bis zu
    30 s Warten auf eine Sperre statt 5 s, und das Schema nur einmal je Datei und Prozess ausführen
    (executescript schreibt und braucht dafür die Schreibsperre)."""
    pfad = Path(pfad or config.DB_PFAD)
    im_speicher = str(pfad) == ":memory:"
    if not im_speicher:
        pfad.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(pfad, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if im_speicher:
        _einrichten(conn)
        return conn
    schluessel = (str(pfad.resolve()), pfad.stat().st_ino)
    if schluessel not in _EINGERICHTET:
        with _EINRICHTEN:
            if schluessel not in _EINGERICHTET:
                conn.execute("PRAGMA journal_mode = WAL")
                _einrichten(conn)
                _EINGERICHTET.add(schluessel)
    return conn


def _einrichten(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text())
    _nachtragen(conn)


def _nachtragen(conn: sqlite3.Connection) -> None:
    """Fehlende Spalten in bestehenden Datenbanken ergänzen."""
    for tabelle, spalte, definition in NACHTRAEGE:
        vorhanden = {z[1] for z in conn.execute(f"PRAGMA table_info({tabelle})")}
        if spalte not in vorhanden:
            conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {definition}")
    conn.commit()


def sitzung() -> Iterator[sqlite3.Connection]:
    """Verbindung für eine Anfrage (FastAPI-Dependency)."""
    conn = verbinden()
    try:
        yield conn
    finally:
        conn.close()
