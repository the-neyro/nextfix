"""Service: Tracking-Liste für Position Tracking (gewählte Suchbegriffe mit Tags).

Ist die Liste leer, wertet Position Tracking alle Suchbegriffe aus der
Search Console aus. Sobald Begriffe drinstehen, zählen nur diese – auch solche,
für die (noch) keine Daten da sind (sie ziehen die Sichtbarkeit nach unten,
wie in Semrush).
"""

import sqlite3

from app.core import projekte

MAX_LAENGE = 200


class TrackingFehler(ValueError):
    """Ungültige Eingabe."""


def normalisieren(text: str) -> str:
    """' SEO  Tool ' → 'seo tool' (GSC liefert Suchbegriffe klein geschrieben)."""
    return " ".join(text.split()).lower()


def _liste(werte: list[str] | str | None) -> list[str]:
    """Liste oder Text (Zeilen/Kommas) → bereinigte, eindeutige Einträge in Reihenfolge."""
    if werte is None:
        return []
    if isinstance(werte, str):
        werte = werte.replace(",", "\n").splitlines()
    ergebnis = []
    for w in werte:
        w = normalisieren(w)
        if len(w) > MAX_LAENGE:
            raise TrackingFehler(f"Zu lang (max. {MAX_LAENGE} Zeichen): {w[:40]}…")
        if w and w not in ergebnis:
            ergebnis.append(w)
    return ergebnis


def hinzufuegen(conn: sqlite3.Connection, projekt_id: int, queries: list[str] | str,
                tags: list[str] | str | None = None) -> dict:
    """Begriffe aufnehmen (vorhandene bleiben) und Tags ergänzen."""
    projekte.holen(conn, projekt_id)
    queries = _liste(queries)
    if not queries:
        raise TrackingFehler("Keine Suchbegriffe angegeben")
    neu = 0
    for q in queries:
        neu += conn.execute("INSERT OR IGNORE INTO tracking_keywords (projekt_id, query) VALUES (?, ?)",
                            (projekt_id, q)).rowcount
    _tags_schreiben(conn, projekt_id, queries, _liste(tags), [])
    conn.commit()
    return {"neu": neu, "vorhanden": len(queries) - neu}


def entfernen(conn: sqlite3.Connection, projekt_id: int, queries: list[str] | str) -> int:
    projekte.holen(conn, projekt_id)
    anzahl = 0
    for q in _liste(queries):
        anzahl += conn.execute("DELETE FROM tracking_keywords WHERE projekt_id = ? AND query = ?",
                               (projekt_id, q)).rowcount
    conn.commit()
    return anzahl


def tags_aendern(conn: sqlite3.Connection, projekt_id: int, queries: list[str] | str,
                 hinzu: list[str] | str | None = None, weg: list[str] | str | None = None) -> None:
    """Tags bei getrackten Begriffen ergänzen bzw. entfernen. Nicht getrackte Begriffe werden ignoriert."""
    projekte.holen(conn, projekt_id)
    _tags_schreiben(conn, projekt_id, _liste(queries), _liste(hinzu), _liste(weg))
    conn.commit()


def _tags_schreiben(conn, projekt_id: int, queries: list[str], hinzu: list[str], weg: list[str]) -> None:
    for q in queries:
        getrackt = conn.execute("SELECT 1 FROM tracking_keywords WHERE projekt_id = ? AND query = ?",
                                (projekt_id, q)).fetchone()
        if not getrackt:
            continue
        for t in hinzu:
            conn.execute("INSERT OR IGNORE INTO tracking_tags (projekt_id, query, tag) VALUES (?, ?, ?)",
                         (projekt_id, q, t))
        for t in weg:
            conn.execute("DELETE FROM tracking_tags WHERE projekt_id = ? AND query = ? AND tag = ?",
                         (projekt_id, q, t))


def liste(conn: sqlite3.Connection, projekt_id: int, tag: str | None = None) -> list[dict]:
    """Getrackte Begriffe mit Tags, optional nur mit einem Tag."""
    projekte.holen(conn, projekt_id)
    zeilen = conn.execute(
        "SELECT k.query, k.angelegt_am, GROUP_CONCAT(t.tag, '\n') tags FROM tracking_keywords k"
        " LEFT JOIN tracking_tags t ON t.projekt_id = k.projekt_id AND t.query = k.query"
        " WHERE k.projekt_id = ? GROUP BY k.query ORDER BY k.query", (projekt_id,)).fetchall()
    ergebnis = [{"query": z["query"], "angelegt_am": z["angelegt_am"],
                 "tags": sorted(z["tags"].split("\n")) if z["tags"] else []} for z in zeilen]
    if tag:
        tag = normalisieren(tag)
        ergebnis = [k for k in ergebnis if tag in k["tags"]]
    return ergebnis


def alle_tags(conn: sqlite3.Connection, projekt_id: int) -> list[dict]:
    zeilen = conn.execute("SELECT tag, COUNT(*) n FROM tracking_tags WHERE projekt_id = ? GROUP BY tag ORDER BY tag",
                          (projekt_id,)).fetchall()
    return [{"tag": z["tag"], "anzahl": z["n"]} for z in zeilen]
