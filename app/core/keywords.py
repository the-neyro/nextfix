"""Service: Keyword-Recherche (Phase 5), angelehnt an das Keyword Magic Tool von Semrush.

Ein Hauptbegriff (Seed) → Ideen aus Google Suggest (A–Z, W-Fragen, Zusätze) und aus den
eigenen Search-Console-Daten des Projekts. Jede Idee bekommt Suchintention, Gruppe,
Wortzahl, Frage ja/nein und – falls vorhanden – eigene Klicks/Impressionen/Position (90 Tage).

Suchvolumen: auf Knopfdruck als Bing-Impressionen pro Monat (GetKeywordStats, braucht den Bing-Schlüssel;
sonst Testwerte), für die wichtigsten Ideen (max. 200 pro Lauf). Echtes Google-Volumen bräuchte Google Ads.
Beides läuft im Hintergrund, weil Suggest und Bing gedrosselt abgefragt werden.
"""

import json
import sqlite3
import threading
from contextlib import closing
from datetime import date, timedelta

from app import gsc
from app.core import projekte
from app.db import verbinden
from app.keywords import analyse
from app.gsc.fehler import GscFehler
from app.keywords.suggest import Suggest, SuggestFehler, erweiterungen, teil_erweiterungen
from app.keywords.volumen import VOLUMEN_QUELLEN

VERWAIST_NACH_SEKUNDEN = 120
GSC_TAGE = 90
VOLUMEN_LIMIT = 200
WENIG_IDEEN = 20       # darunter werden Teilphrasen nachgefragt (Nischen-/Lokal-Begriffe)
SORTIERUNGEN = {
    "volumen": "COALESCE(volumen, -1) DESC, keyword",
    "impressionen": "COALESCE(gsc_impressionen, -1) DESC, keyword",
    "keyword": "keyword",
    "woerter": "woerter, keyword",
    "position": "COALESCE(gsc_position, 999), keyword",
}

# austauschbar für Tests (z. B. ohne Pause und mit nachgebautem Google)
SUGGEST_FABRIK = Suggest


class KeywordFehler(ValueError):
    """Ungültige Eingabe, Recherche läuft schon o. Ä."""


def _seed_pruefen(seed: str) -> str:
    seed = " ".join((seed or "").split()).lower()
    if not 2 <= len(seed) <= 80:
        raise KeywordFehler("Hauptbegriff muss 2 bis 80 Zeichen lang sein")
    return seed


def holen(conn: sqlite3.Connection, recherche_id: int) -> dict:
    z = conn.execute("SELECT * FROM recherchen WHERE id = ?", (recherche_id,)).fetchone()
    if z is None:
        raise KeywordFehler(f"Recherche {recherche_id} nicht gefunden")
    return dict(z)


def liste(conn: sqlite3.Connection, projekt_id: int) -> list[dict]:
    projekte.holen(conn, projekt_id)
    _verwaiste_schliessen(conn)
    return [dict(z) for z in conn.execute("SELECT * FROM recherchen WHERE projekt_id = ? ORDER BY id DESC",
                                          (projekt_id,))]


def loeschen(conn: sqlite3.Connection, recherche_id: int) -> None:
    holen(conn, recherche_id)
    conn.execute("DELETE FROM recherchen WHERE id = ?", (recherche_id,))
    conn.commit()


def _verwaiste_schliessen(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE recherchen SET status = 'fehler', beendet_am = datetime('now'),"
        " fehler_text = 'Recherche wurde beendet (kein Lebenszeichen)'"
        " WHERE status = 'laeuft' AND (julianday('now') - julianday(COALESCE(lebenszeichen, angelegt_am))) * 86400 > ?",
        (VERWAIST_NACH_SEKUNDEN,))
    conn.execute(
        "UPDATE recherchen SET volumen_status = 'fehler', volumen_fehler = 'Abfrage wurde beendet (kein Lebenszeichen)'"
        " WHERE volumen_status = 'laeuft' AND (julianday('now') - julianday(volumen_lebenszeichen)) * 86400 > ?",
        (VERWAIST_NACH_SEKUNDEN,))
    conn.commit()


def starten(conn: sqlite3.Connection, projekt_id: int, seed: str, sprache: str = "de", land: str = "de",
            warten: bool = False) -> dict:
    """Neue Recherche anlegen und im Hintergrund ausführen (warten=True: blockierend)."""
    projekte.holen(conn, projekt_id)
    seed = _seed_pruefen(seed)
    _verwaiste_schliessen(conn)
    laufend = conn.execute("SELECT id FROM recherchen WHERE projekt_id = ? AND status = 'laeuft'",
                           (projekt_id,)).fetchone()
    if laufend:
        raise KeywordFehler(f"Recherche {laufend['id']} läuft noch. Bitte abwarten.")
    rid = conn.execute(
        "INSERT INTO recherchen (projekt_id, seed, sprache, land, schritte_gesamt, lebenszeichen)"
        " VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (projekt_id, seed, sprache.lower(), land.lower(), len(erweiterungen(seed)))).lastrowid
    conn.commit()
    if warten:
        _ausfuehren(rid)
    else:
        threading.Thread(target=_ausfuehren, args=(rid,), daemon=True).start()
    return holen(conn, rid)


def _ausfuehren(recherche_id: int) -> None:
    with closing(verbinden()) as conn:
        r = holen(conn, recherche_id)
        seed = r["seed"]
        gefunden: dict[str, set[str]] = {seed: {"suggest"}}
        fehler = None
        try:
            s = SUGGEST_FABRIK(conn, r["sprache"], r["land"])
            anfragen = erweiterungen(seed)
            i = 0
            while i < len(anfragen):
                for v in s.vorschlaege(anfragen[i]):
                    if _passt(v, seed, streng=i >= len(erweiterungen(seed))):
                        gefunden.setdefault(v, set()).add("suggest")
                i += 1
                if i == len(anfragen) == len(erweiterungen(seed)) and len(gefunden) < WENIG_IDEEN:
                    anfragen += teil_erweiterungen(seed)  # Nische: Teilphrasen nachschieben
                conn.execute("UPDATE recherchen SET schritte_fertig = ?, schritte_gesamt = ?, ideen = ?,"
                             " lebenszeichen = datetime('now') WHERE id = ?", (i, len(anfragen), len(gefunden), recherche_id))
                conn.commit()
        except SuggestFehler as e:
            fehler = str(e)
        except Exception as e:  # nie in 'laeuft' hängen bleiben
            fehler = f"{type(e).__name__}: {e}"
        try:
            eigene = _gsc_daten(conn, r["projekt_id"], seed)
            for k in eigene:
                gefunden.setdefault(k, set()).add("gsc")
            _speichern(conn, recherche_id, seed, gefunden, eigene, projekte.holen(conn, r["projekt_id"]).domain)
        except Exception as e:
            if conn.in_transaction:
                conn.rollback()
            fehler = fehler or f"{type(e).__name__}: {e}"
        conn.execute("UPDATE recherchen SET status = ?, fehler_text = ?, beendet_am = datetime('now'),"
                     " ideen = (SELECT COUNT(*) FROM recherche_ideen WHERE recherche_id = ?) WHERE id = ?",
                     ("fehler" if fehler else "fertig", fehler, recherche_id, recherche_id))
        conn.commit()


def _passt(vorschlag: str, seed: str, streng: bool = False) -> bool:
    """Suggest liefert bei „seed x“ auch Fremdes. Behalten, wenn ein Wort des Hauptbegriffs drinsteckt.
    streng (Teilphrasen-Anfragen): das längste Wort, alle kurzen Wörter (≤ 3 Zeichen, meist das Thema wie
    „ki“, „seo“) und alle bis auf eines müssen drinstecken. Kurze Wörter zählen nur als ganzes Wort."""
    if not analyse.lesbar(vorschlag):
        return False
    if seed in vorschlag:
        return True
    tokens = set(analyse.woerter(vorschlag))
    woerter = [w for w in analyse.woerter(seed) if w not in analyse.STOPWOERTER and len(w) > 1]
    if not woerter:
        return False

    def drin(w: str) -> bool:
        return w in tokens or (len(w) > 3 and w in vorschlag)  # lange Wörter auch in Komposita

    treffer = sum(drin(w) for w in woerter)
    if streng:
        pflicht = [max(woerter, key=len)] + [w for w in woerter if len(w) <= 3]
        return all(drin(w) for w in pflicht) and treffer >= max(1, len(woerter) - 1)
    return treffer >= 1


def _gsc_daten(conn, projekt_id: int, seed: str) -> dict[str, dict]:
    """Eigene Google-Daten (letzte 90 Tage ab neuestem Tag) für Suchbegriffe mit Wörtern des Hauptbegriffs."""
    quellen = [q for q, m in gsc.SUCHMASCHINE.items() if m == "google"]
    platz = ",".join("?" * len(quellen))
    neuester = conn.execute(f"SELECT MAX(datum) FROM gsc_zeilen WHERE projekt_id = ? AND quelle IN ({platz})",
                            [projekt_id, *quellen]).fetchone()[0]
    if not neuester:
        return {}
    von = (date.fromisoformat(neuester) - timedelta(days=GSC_TAGE - 1)).isoformat()
    zeilen = conn.execute(
        "SELECT query, SUM(klicks) k, SUM(impressionen) i, SUM(position * impressionen) p FROM gsc_zeilen"
        f" WHERE projekt_id = ? AND quelle IN ({platz}) AND datum >= ? GROUP BY query",
        [projekt_id, *quellen, von]).fetchall()
    return {z["query"]: {"klicks": z["k"], "impressionen": z["i"], "position": round(z["p"] / z["i"], 1)}
            for z in zeilen if z["i"] and _passt(z["query"], seed)}


def _speichern(conn, recherche_id: int, seed: str, gefunden: dict[str, set[str]], eigene: dict[str, dict],
               domain: str) -> None:
    marke = domain.removeprefix("www.").split(".")[0]
    gruppen = analyse.gruppieren(list(gefunden), seed)
    conn.execute("DELETE FROM recherche_ideen WHERE recherche_id = ?", (recherche_id,))
    conn.executemany(
        "INSERT INTO recherche_ideen (recherche_id, keyword, quellen, intent, gruppe, woerter, frage,"
        " gsc_impressionen, gsc_klicks, gsc_position) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(recherche_id, k, ",".join(sorted(q)), analyse.intent(k, marke), gruppen[k], len(analyse.woerter(k)),
          int(analyse.ist_frage(k)), (eigene.get(k) or {}).get("impressionen"), (eigene.get(k) or {}).get("klicks"),
          (eigene.get(k) or {}).get("position")) for k, q in gefunden.items()])
    conn.commit()


def ideen(conn: sqlite3.Connection, recherche_id: int, gruppe: str | None = None, intent: str | None = None,
          suche: str | None = None, nur_fragen: bool = False, sortierung: str = "impressionen",
          limit: int = 500, offset: int = 0) -> dict:
    """Ideen einer Recherche mit Filtern, dazu Gruppen- und Intent-Zähler (für die Seitenleiste)."""
    r = holen(conn, recherche_id)
    if sortierung not in SORTIERUNGEN:
        raise KeywordFehler(f"Unbekannte Sortierung: {sortierung} ({' | '.join(SORTIERUNGEN)})")
    if intent and intent not in analyse.INTENTS:
        raise KeywordFehler(f"Unbekannter Intent: {intent} ({' | '.join(analyse.INTENTS)})")
    sql, werte = " WHERE recherche_id = ?", [recherche_id]
    for bedingung, wert in [("gruppe = ?", gruppe), ("intent = ?", intent), ("keyword LIKE ?", suche and f"%{suche.lower()}%")]:
        if wert:
            sql += f" AND {bedingung}"
            werte.append(wert)
    if nur_fragen:
        sql += " AND frage = 1"
    gesamt = conn.execute(f"SELECT COUNT(*) FROM recherche_ideen{sql}", werte).fetchone()[0]
    zeilen = conn.execute(f"SELECT * FROM recherche_ideen{sql} ORDER BY {SORTIERUNGEN[sortierung]} LIMIT ? OFFSET ?",
                          [*werte, limit, offset]).fetchall()
    gruppen = conn.execute("SELECT gruppe, COUNT(*) n FROM recherche_ideen WHERE recherche_id = ?"
                           " GROUP BY gruppe ORDER BY gruppe IN ('sonstige', '(Hauptbegriff)'), n DESC, gruppe",
                           (recherche_id,)).fetchall()
    intents = dict(conn.execute("SELECT intent, COUNT(*) FROM recherche_ideen WHERE recherche_id = ? GROUP BY intent",
                                (recherche_id,)).fetchall())
    fragen = conn.execute("SELECT COUNT(*) FROM recherche_ideen WHERE recherche_id = ? AND frage = 1",
                          (recherche_id,)).fetchone()[0]
    return {"recherche": r, "gesamt": gesamt,
            "ideen": [dict(z, quellen=z["quellen"].split(","), frage=bool(z["frage"]),
                           trend=json.loads(z["trend"]) if z["trend"] else None) for z in zeilen],
            "gruppen": [{"gruppe": g["gruppe"], "anzahl": g["n"]} for g in gruppen],
            "intents": {i: intents.get(i, 0) for i in analyse.INTENTS}, "fragen": fragen}


# ---------- Suchvolumen (Bing) ----------

def volumen_starten(conn: sqlite3.Connection, recherche_id: int, quelle: str = "bing", limit: int = VOLUMEN_LIMIT,
                    warten: bool = False) -> dict:
    """Bing-Impressionen/Monat für die wichtigsten Ideen ohne Wert holen (eigene GSC-Impressionen, dann kurze
    Begriffe zuerst). quelle: bing (Schlüssel nötig) | bing_mock (Testwerte)."""
    r = holen(conn, recherche_id)
    if quelle not in VOLUMEN_QUELLEN:
        raise KeywordFehler(f"Unbekannte Volumen-Quelle: {quelle} ({' | '.join(VOLUMEN_QUELLEN)})")
    if not 1 <= limit <= 1000:
        raise KeywordFehler("limit muss zwischen 1 und 1000 liegen")
    _verwaiste_schliessen(conn)
    r = holen(conn, recherche_id)
    if r["status"] == "laeuft" or r["volumen_status"] == "laeuft":
        raise KeywordFehler("Recherche läuft noch. Bitte abwarten.")
    offen = conn.execute("SELECT COUNT(*) FROM recherche_ideen WHERE recherche_id = ?"
                         " AND (volumen_quelle IS NULL OR volumen_quelle != ?)", (recherche_id, quelle)).fetchone()[0]
    conn.execute("UPDATE recherchen SET volumen_status = 'laeuft', volumen_fertig = 0, volumen_gesamt = ?,"
                 " volumen_fehler = NULL, volumen_lebenszeichen = datetime('now') WHERE id = ?",
                 (min(limit, offen), recherche_id))
    conn.commit()
    if warten:
        _volumen_ausfuehren(recherche_id, quelle, limit)
    else:
        threading.Thread(target=_volumen_ausfuehren, args=(recherche_id, quelle, limit), daemon=True).start()
    return holen(conn, recherche_id)


def _volumen_ausfuehren(recherche_id: int, quelle: str, limit: int) -> None:
    with closing(verbinden()) as conn:
        r = holen(conn, recherche_id)
        fehler = None
        try:
            v = VOLUMEN_QUELLEN[quelle](conn, r["land"], r["sprache"])
            begriffe = [z["keyword"] for z in conn.execute(
                "SELECT keyword FROM recherche_ideen WHERE recherche_id = ? AND (volumen_quelle IS NULL"
                " OR volumen_quelle != ?) ORDER BY COALESCE(gsc_impressionen, -1) DESC, woerter, keyword LIMIT ?",
                (recherche_id, quelle, limit))]
            for i, k in enumerate(begriffe, start=1):
                w = v.holen(k)
                conn.execute("UPDATE recherche_ideen SET volumen = ?, volumen_quelle = ?, trend = ?"
                             " WHERE recherche_id = ? AND keyword = ?",
                             (w["monat"], quelle, json.dumps(w["verlauf"]), recherche_id, k))
                conn.execute("UPDATE recherchen SET volumen_fertig = ?, volumen_lebenszeichen = datetime('now')"
                             " WHERE id = ?", (i, recherche_id))
                conn.commit()
        except GscFehler as e:
            fehler = str(e)
        except Exception as e:
            fehler = f"{type(e).__name__}: {e}"
        if conn.in_transaction:
            conn.commit()
        conn.execute("UPDATE recherchen SET volumen_status = ?, volumen_fehler = ? WHERE id = ?",
                     ("fehler" if fehler else "fertig", fehler, recherche_id))
        conn.commit()
