"""Service: Search-Console-Importe im Hintergrund und täglicher Auto-Import.

Ein Import läuft wie ein Crawl im eigenen Thread mit eigener DB-Verbindung und
meldet nach jedem Tag Fortschritt + Lebenszeichen. Pro Projekt läuft höchstens einer.

Auto-Import: Projekte mit Eintrag in auto_importe (je Suchmaschine eine Quelle) werden geprüft, sobald der Planer
läuft (Web-App-Start, dann alle 30 Min.). Fällig ist ein Projekt, wenn der
neueste gespeicherte Tag älter ist als heute minus Verzug. Geholt wird ab dem
neuesten Tag minus 2 (Google korrigiert frische Tage noch), beim ersten Mal
480 Tage (gsc) bzw. 90 Tage (mock).
"""

import logging
import sqlite3
import threading
import time
from contextlib import closing
from datetime import date, timedelta

from app import gsc
from app.core import positionen, projekte
from app.db import verbinden

VERWAIST_NACH_SEKUNDEN = 120   # Thread/Prozess weg, ohne den Import abzuschließen
ERSTER_IMPORT_TAGE = {"gsc": 480, "mock": 90, "bing": 480, "bing_mock": 90}
UEBERLAPPUNG_TAGE = 2
FEHLER_PAUSE_STUNDEN = 6       # nach fehlgeschlagenem Auto-Import so lange nicht erneut versuchen
# Bing liefert Wochenwerte: der neueste Tag ist fast immer „alt“. Nach erfolgreichem Import so lange warten.
ERFOLG_PAUSE_STUNDEN = {"bing": 20, "bing_mock": 20}
PLANER_INTERVALL = 1800

log = logging.getLogger(__name__)


class ImportFehler(ValueError):
    """Import läuft schon, unbekannte Quelle o. Ä."""


# ---------- Einzelne Importe ----------

def holen(conn: sqlite3.Connection, import_id: int) -> dict:
    z = conn.execute("SELECT * FROM gsc_importe WHERE id = ?", (import_id,)).fetchone()
    if z is None:
        raise ImportFehler(f"Import {import_id} nicht gefunden")
    return dict(z)


def liste(conn: sqlite3.Connection, projekt_id: int, limit: int = 10) -> list[dict]:
    projekte.holen(conn, projekt_id)
    _verwaiste_schliessen(conn, projekt_id)
    zeilen = conn.execute("SELECT * FROM gsc_importe WHERE projekt_id = ? ORDER BY id DESC LIMIT ?",
                          (projekt_id, limit)).fetchall()
    return [dict(z) for z in zeilen]


def letzter(conn: sqlite3.Connection, projekt_id: int) -> dict | None:
    eintraege = liste(conn, projekt_id, 1)
    return eintraege[0] if eintraege else None


def _verwaiste_schliessen(conn: sqlite3.Connection, projekt_id: int) -> None:
    conn.execute(
        "UPDATE gsc_importe SET status = 'fehler', beendet_am = datetime('now'),"
        " fehler_text = 'Import-Prozess wurde beendet (kein Lebenszeichen). Gespeicherte Tage bleiben erhalten.'"
        " WHERE projekt_id = ? AND status = 'laeuft'"
        " AND (julianday('now') - julianday(COALESCE(lebenszeichen, gestartet_am))) * 86400 > ?",
        (projekt_id, VERWAIST_NACH_SEKUNDEN))
    conn.commit()


def starten(conn: sqlite3.Connection, projekt_id: int, quelle: str = "mock", tage: int = 90,
            von: date | None = None, bis: date | None = None, ausloeser: str = "hand",
            warten: bool = False) -> dict:
    """Legt einen Import an und führt ihn im Hintergrund aus (warten=True: blockierend)."""
    projekte.holen(conn, projekt_id)
    if quelle not in gsc.QUELLEN:
        raise ImportFehler(f"Unbekannte Quelle: {quelle} ({' | '.join(gsc.QUELLEN)})")
    try:
        von, bis = positionen.zeitraum_pruefen(tage, bis, von)
    except positionen.PositionenFehler as e:
        raise ImportFehler(str(e)) from None
    _verwaiste_schliessen(conn, projekt_id)
    laufend = conn.execute("SELECT id FROM gsc_importe WHERE projekt_id = ? AND status = 'laeuft'",
                           (projekt_id,)).fetchone()
    if laufend:
        raise ImportFehler(f"Import {laufend['id']} läuft noch. Bitte abwarten.")
    import_id = conn.execute(
        "INSERT INTO gsc_importe (projekt_id, quelle, ausloeser, von, bis, tage_gesamt, lebenszeichen)"
        " VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        (projekt_id, quelle, ausloeser, von.isoformat(), bis.isoformat(), (bis - von).days + 1)).lastrowid
    conn.commit()
    if warten:
        _ausfuehren(import_id)
    else:
        threading.Thread(target=_ausfuehren, args=(import_id,), daemon=True).start()
    return holen(conn, import_id)


def _ausfuehren(import_id: int) -> None:
    """Eigener Thread, eigene Verbindung. Hinterlässt den Import nie in 'laeuft'."""
    with closing(verbinden()) as conn:
        imp = holen(conn, import_id)

        def fortschritt(fertig: int, gesamt: int, zeilen: int) -> None:
            conn.execute("UPDATE gsc_importe SET tage_fertig = ?, zeilen = ?, lebenszeichen = datetime('now')"
                         " WHERE id = ?", (fertig, zeilen, import_id))
            conn.commit()

        try:
            r = positionen.importieren(conn, imp["projekt_id"], imp["quelle"], von=date.fromisoformat(imp["von"]),
                                       bis=date.fromisoformat(imp["bis"]), fortschritt=fortschritt)
            conn.execute("UPDATE gsc_importe SET status = 'fertig', zeilen = ?, property = ?,"
                         " beendet_am = datetime('now') WHERE id = ?", (r["zeilen"], r["property"], import_id))
        except Exception as e:  # jeder Fehler landet im Import, nicht im Nichts
            if conn.in_transaction:
                conn.rollback()
            text = str(e) if isinstance(e, positionen.PositionenFehler) else f"{type(e).__name__}: {e}"
            conn.execute("UPDATE gsc_importe SET status = 'fehler', fehler_text = ?, beendet_am = datetime('now')"
                         " WHERE id = ?", (text[:500], import_id))
        conn.commit()


# ---------- Auto-Import ----------

def auto_holen(conn: sqlite3.Connection, projekt_id: int) -> dict:
    """Auto-Import je Suchmaschine: {"google": "gsc" | "mock" | None, "bing": "bing" | "bing_mock" | None}."""
    zeilen = conn.execute("SELECT suchmaschine, quelle FROM auto_importe WHERE projekt_id = ?", (projekt_id,))
    ergebnis = {m: None for m in positionen.SUCHMASCHINEN}
    ergebnis.update({z["suchmaschine"]: z["quelle"] for z in zeilen})
    return ergebnis


def auto_setzen(conn: sqlite3.Connection, projekt_id: int, quelle: str | None,
                suchmaschine: str | None = None) -> dict:
    """Täglichen Auto-Import einer Suchmaschine einschalten (quelle, z. B. gsc oder bing_mock) oder ausschalten
    (quelle leer, dann suchmaschine angeben). Pro Suchmaschine gilt höchstens eine Quelle."""
    projekte.holen(conn, projekt_id)
    if quelle and quelle not in gsc.QUELLEN:
        raise ImportFehler(f"Unbekannte Quelle: {quelle} ({' | '.join(gsc.QUELLEN)})")
    maschine = gsc.SUCHMASCHINE[quelle] if quelle else suchmaschine
    if maschine not in positionen.SUCHMASCHINEN:
        raise ImportFehler(f"Suchmaschine angeben ({' | '.join(positionen.SUCHMASCHINEN)})")
    if suchmaschine and suchmaschine != maschine:
        raise ImportFehler(f"Quelle {quelle} gehört nicht zu {suchmaschine}")
    conn.execute("DELETE FROM auto_importe WHERE projekt_id = ? AND suchmaschine = ?", (projekt_id, maschine))
    if quelle:
        conn.execute("INSERT INTO auto_importe (projekt_id, suchmaschine, quelle) VALUES (?, ?, ?)",
                     (projekt_id, maschine, quelle))
    conn.commit()
    return auto_holen(conn, projekt_id)


def faellig(conn: sqlite3.Connection, heute: date | None = None) -> list[dict]:
    """Welche Projekte brauchen einen Auto-Import, und für welchen Zeitraum?"""
    heute = heute or date.today()
    bis = heute - timedelta(days=positionen.VERZUG_TAGE)
    ergebnis = []
    for a in conn.execute("SELECT projekt_id, quelle FROM auto_importe ORDER BY projekt_id, suchmaschine").fetchall():
        pid, quelle = a["projekt_id"], a["quelle"]
        _verwaiste_schliessen(conn, pid)
        if conn.execute("SELECT 1 FROM gsc_importe WHERE projekt_id = ? AND status = 'laeuft'", (pid,)).fetchone():
            continue
        fehler_kuerzlich = conn.execute(
            "SELECT 1 FROM gsc_importe WHERE projekt_id = ? AND ausloeser = 'auto' AND status = 'fehler'"
            " AND id = (SELECT MAX(id) FROM gsc_importe WHERE projekt_id = ? AND ausloeser = 'auto' AND quelle = ?)"
            " AND (julianday('now') - julianday(gestartet_am)) * 24 < ?",
            (pid, pid, quelle, FEHLER_PAUSE_STUNDEN)).fetchone()
        if fehler_kuerzlich:
            continue
        pause = ERFOLG_PAUSE_STUNDEN.get(quelle)
        if pause and conn.execute(
                "SELECT 1 FROM gsc_importe WHERE projekt_id = ? AND quelle = ? AND status = 'fertig'"
                " AND (julianday('now') - julianday(beendet_am)) * 24 < ?", (pid, quelle, pause)).fetchone():
            continue
        neuester = conn.execute("SELECT MAX(datum) FROM gsc_zeilen WHERE projekt_id = ? AND quelle = ?",
                                (pid, quelle)).fetchone()[0]
        if neuester is None:
            von = bis - timedelta(days=ERSTER_IMPORT_TAGE.get(quelle, 90) - 1)
        elif date.fromisoformat(neuester) >= bis:
            continue
        else:
            von = date.fromisoformat(neuester) - timedelta(days=UEBERLAPPUNG_TAGE)
        von = max(von, bis - timedelta(days=479))
        ergebnis.append({"projekt_id": pid, "quelle": quelle, "von": von.isoformat(), "bis": bis.isoformat()})
    return ergebnis


def auto_lauf(conn: sqlite3.Connection, heute: date | None = None) -> list[dict]:
    """Alle fälligen Auto-Importe nacheinander ausführen (blockierend). Gibt die Importe zurück."""
    erledigt = []
    for f in faellig(conn, heute):
        try:
            erledigt.append(starten(conn, f["projekt_id"], f["quelle"], von=date.fromisoformat(f["von"]),
                                    bis=date.fromisoformat(f["bis"]), ausloeser="auto", warten=True))
        except ImportFehler as e:  # z. B. inzwischen läuft ein Hand-Import
            log.warning("Auto-Import Projekt %s übersprungen: %s", f["projekt_id"], e)
    return [holen(conn, i["id"]) for i in erledigt]


def planer_starten(intervall: int = PLANER_INTERVALL) -> threading.Thread:
    """Hintergrund-Thread: prüft beim Start und dann regelmäßig auf fällige Auto-Importe."""
    def schleife():
        while True:
            try:
                with closing(verbinden()) as conn:
                    for i in auto_lauf(conn):
                        log.info("Auto-Import %s (Projekt %s): %s, %s Zeilen",
                                 i["id"], i["projekt_id"], i["status"], i["zeilen"])
            except Exception:
                log.exception("Auto-Import-Planer")
            time.sleep(intervall)

    t = threading.Thread(target=schleife, name="auto-import", daemon=True)
    t.start()
    return t
