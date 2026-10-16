"""Service: Core Web Vitals für die wichtigsten Seiten eines Crawls messen (im Hintergrund).

Auswahl wie Semrush (Stichprobe statt alle Seiten): Startseite, dann HTML-Seiten mit der höchsten
internen Link-Stärke. Ergebnis je Seite und Gerät plus Zusammenfassung (Anteil „gut“, Medianwerte).
Fließt (noch) nicht in den Health-Score ein, weil die Messung nach dem Crawl läuft.
"""

import sqlite3
import statistics
import threading
from contextlib import closing

from app.core import audit
from app.crawler import vitals as messung
from app.db import verbinden

VERWAIST_NACH_SEKUNDEN = 180
MAX_SEITEN = 30
METRIKEN = ("lcp", "cls", "tbt", "fcp", "ttfb")

# austauschbar für Tests (z. B. ohne Drosselung)
MESSER_FABRIK = messung.Messer


class VitalsFehler(ValueError):
    """Kein fertiger Crawl, Messung läuft schon o. Ä."""


def seiten_auswahl(conn: sqlite3.Connection, crawl_id: int, anzahl: int) -> list[str]:
    crawl = audit.crawl_holen(conn, crawl_id)
    zeilen = conn.execute(
        "SELECT url FROM seiten WHERE crawl_id = ? AND status_code = 200 AND woerter IS NOT NULL AND blockiert = 0"
        " ORDER BY url = ? DESC, COALESCE(link_rank, 0) DESC, tiefe, url LIMIT ?",
        (crawl_id, crawl["start_url"], anzahl)).fetchall()
    return [z["url"] for z in zeilen]


def _verwaiste_schliessen(conn) -> None:
    conn.execute("UPDATE vitals_laeufe SET status = 'fehler', beendet_am = datetime('now'),"
                 " fehler_text = 'Messung wurde beendet (kein Lebenszeichen)' WHERE status = 'laeuft'"
                 " AND (julianday('now') - julianday(COALESCE(lebenszeichen, gestartet_am))) * 86400 > ?",
                 (VERWAIST_NACH_SEKUNDEN,))
    conn.commit()


def starten(conn: sqlite3.Connection, crawl_id: int, anzahl: int = 10, geraete: tuple[str, ...] = ("mobile", "desktop"),
            warten: bool = False) -> dict:
    """Misst `anzahl` Seiten je Gerät (Standard 10 × mobil + Desktop, ca. 1–2 Min.)."""
    crawl = audit.crawl_holen(conn, crawl_id)
    if crawl["status"] == "laeuft":
        raise VitalsFehler("Crawl läuft noch – erst danach messen")
    if not 1 <= anzahl <= MAX_SEITEN:
        raise VitalsFehler(f"anzahl muss zwischen 1 und {MAX_SEITEN} liegen")
    unbekannt = set(geraete) - set(messung.GERAETE)
    if unbekannt or not geraete:
        raise VitalsFehler(f"Geräte: {' | '.join(messung.GERAETE)}")
    _verwaiste_schliessen(conn)
    if conn.execute("SELECT 1 FROM vitals_laeufe WHERE status = 'laeuft'").fetchone():
        raise VitalsFehler("Es läuft schon eine Messung (eine gleichzeitig, damit die Werte nicht verfälscht werden)")
    urls = seiten_auswahl(conn, crawl_id, anzahl)
    if not urls:
        raise VitalsFehler("Keine messbaren HTML-Seiten im Crawl")
    lauf_id = conn.execute("INSERT INTO vitals_laeufe (crawl_id, gesamt, lebenszeichen) VALUES (?, ?, datetime('now'))",
                           (crawl_id, len(urls) * len(geraete))).lastrowid
    conn.commit()
    args = (lauf_id, urls, tuple(geraete))
    if warten:
        _ausfuehren(*args)
    else:
        threading.Thread(target=_ausfuehren, args=args, daemon=True).start()
    return lauf_holen(conn, lauf_id)


def _ausfuehren(lauf_id: int, urls: list[str], geraete: tuple[str, ...]) -> None:
    with closing(verbinden()) as conn:
        fehler = None
        try:
            with MESSER_FABRIK() as m:
                n = 0
                for url in urls:
                    for g in geraete:
                        e = m.messen(url, g)
                        conn.execute(
                            "INSERT OR REPLACE INTO vitals (lauf_id, url, geraet, ttfb, fcp, lcp, cls, tbt, bytes, anfragen,"
                            " score, fehler) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (lauf_id, url, g, e.ttfb, e.fcp, e.lcp, e.cls, e.tbt, e.bytes, e.anfragen, e.score, e.fehler))
                        n += 1
                        conn.execute("UPDATE vitals_laeufe SET fertig = ?, lebenszeichen = datetime('now') WHERE id = ?",
                                     (n, lauf_id))
                        conn.commit()
        except Exception as e:  # z. B. Chromium fehlt
            fehler = f"{type(e).__name__}: {str(e).splitlines()[0][:300]}"
        conn.execute("UPDATE vitals_laeufe SET status = ?, fehler_text = ?, beendet_am = datetime('now') WHERE id = ?",
                     ("fehler" if fehler else "fertig", fehler, lauf_id))
        conn.commit()


def lauf_holen(conn: sqlite3.Connection, lauf_id: int) -> dict:
    z = conn.execute("SELECT * FROM vitals_laeufe WHERE id = ?", (lauf_id,)).fetchone()
    if z is None:
        raise VitalsFehler(f"Messlauf {lauf_id} nicht gefunden")
    return dict(z)


def ergebnis(conn: sqlite3.Connection, crawl_id: int) -> dict:
    """Letzter Messlauf des Crawls: Werte je Seite/Gerät mit Ampel, Zusammenfassung je Gerät."""
    audit.crawl_holen(conn, crawl_id)
    _verwaiste_schliessen(conn)
    z = conn.execute("SELECT id FROM vitals_laeufe WHERE crawl_id = ? ORDER BY id DESC LIMIT 1", (crawl_id,)).fetchone()
    if z is None:
        return {"lauf": None, "messungen": [], "zusammenfassung": {}}
    lauf = lauf_holen(conn, z["id"])
    messungen = []
    for r in conn.execute("SELECT * FROM vitals WHERE lauf_id = ? ORDER BY url, geraet DESC", (lauf["id"],)):
        d = dict(r)
        d["bewertung"] = {k: messung.bewertung(k, d[k]) for k in METRIKEN}
        messungen.append(d)
    zusammenfassung = {}
    for g in messung.GERAETE:
        ok = [m for m in messungen if m["geraet"] == g and not m["fehler"]]
        if not ok:
            continue
        zusammenfassung[g] = {
            "seiten": len(ok),
            "score": round(statistics.median(m["score"] for m in ok if m["score"] is not None)) if any(
                m["score"] is not None for m in ok) else None,
            **{f"{k}_median": statistics.median(m[k] for m in ok if m[k] is not None) if any(
                m[k] is not None for m in ok) else None for k in METRIKEN},
            # „Core Web Vitals bestanden“ (Labor): LCP und CLS gut, TBT als INP-Ersatz gut
            "bestanden": sum(all(m["bewertung"][k] == "gut" for k in ("lcp", "cls", "tbt")) for m in ok),
        }
    return {"lauf": lauf, "messungen": messungen, "zusammenfassung": zusammenfassung}
