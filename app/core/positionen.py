"""Service: Position Tracking auf Basis der Search-Console-Daten (Tabelle gsc_zeilen).

Zeiträume richten sich nach dem letzten Tag mit Daten, nicht nach heute
(GSC liefert mit 2–3 Tagen Verzug). Verglichen wird immer mit dem gleich
langen Zeitraum direkt davor.

Positionen sind Google-Durchschnitte (gewichtet nach Impressionen), keine
täglichen Momentaufnahmen wie bei Semrush.
"""

import sqlite3
from datetime import date, timedelta

from app import gsc
from app.core import gsc_konto, projekte, tracking
from app.gsc.ctr import erwartete_ctr

VERZUG_TAGE = 3        # GSC-Daten sind frühestens nach ~3 Tagen vollständig
STRIKING = (8, 20)     # „fast auf Seite 1“
KANNIBAL_ANTEIL = 0.1  # zweite Seite zählt ab 10 % der Impressionen
GERAETE = ("DESKTOP", "MOBILE", "TABLET")
AUSWAHL = ("tracking", "alle")
SUCHMASCHINEN = ("google", "bing")


class PositionenFehler(ValueError):
    """Keine Daten oder ungültige Eingabe."""


# ---------- Import ----------

def importieren(conn: sqlite3.Connection, projekt_id: int, quelle: str = "mock", tage: int = 90,
                bis: date | None = None, von: date | None = None, fortschritt=None) -> dict:
    """Holt die Tage von..bis (Standard: `tage` Tage bis heute minus Verzug) Tag für Tag und speichert sie
    (vorhandene Tage werden ersetzt). fortschritt(tage_fertig, tage_gesamt, zeilen) wird nach jedem Tag gerufen."""
    projekt = projekte.holen(conn, projekt_id)
    von, bis = zeitraum_pruefen(tage, bis, von)
    try:
        q = gsc.quelle_holen(quelle)
    except gsc.GscFehler as e:
        raise PositionenFehler(str(e)) from None
    gesamt = (bis - von).days + 1
    anzahl = 0
    try:
        prop = gsc_konto.property_ermitteln(conn, projekt_id, q) if q.name in gsc.MIT_ZUGANG else None
        for i in range(gesamt):
            tag = von + timedelta(days=i)
            zeilen = q.abrufen(projekt.domain, tag, tag, property=prop)
            conn.executemany(
                "INSERT OR REPLACE INTO gsc_zeilen (projekt_id, datum, query, seite, land, geraet, klicks,"
                " impressionen, position, quelle) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(projekt_id, z["datum"], z["query"], z["seite"], z["land"], z["geraet"], z["klicks"],
                  z["impressionen"], z["position"], q.name) for z in zeilen])
            conn.commit()  # pro Tag sichern: Abbruch verliert höchstens einen Tag
            anzahl += len(zeilen)
            if fortschritt:
                fortschritt(i + 1, gesamt, anzahl)
    except gsc.GscFehler as e:
        raise PositionenFehler(str(e)) from None
    return {"quelle": q.name, "property": prop, "von": von.isoformat(), "bis": bis.isoformat(),
            "zeilen": anzahl}


def zeitraum_pruefen(tage: int = 90, bis: date | None = None, von: date | None = None) -> tuple[date, date]:
    """Importzeitraum bestimmen: bis = heute minus Verzug, von = explizit oder `tage` davor; max. 480 Tage."""
    bis = bis or date.today() - timedelta(days=VERZUG_TAGE)
    if von is None:
        if not 1 <= tage <= 480:
            raise PositionenFehler("tage muss zwischen 1 und 480 liegen")
        von = bis - timedelta(days=tage - 1)
    if not 1 <= (bis - von).days + 1 <= 480:
        raise PositionenFehler("Zeitraum muss zwischen 1 und 480 Tagen liegen")
    return von, bis


def daten_loeschen(conn: sqlite3.Connection, projekt_id: int, quelle: str | None = None) -> int:
    """Löscht gespeicherte GSC-Daten (z. B. Mock-Daten, bevor echte kommen)."""
    projekte.holen(conn, projekt_id)
    sql, werte = "DELETE FROM gsc_zeilen WHERE projekt_id = ?", [projekt_id]
    if quelle:
        sql += " AND quelle = ?"
        werte.append(quelle)
    anzahl = conn.execute(sql, werte).rowcount
    conn.commit()
    return anzahl


def _quellen_sql(suchmaschine: str | None) -> tuple[str, list]:
    """SQL-Filter auf die Quellen einer Suchmaschine (Google- und Bing-Daten nie mischen)."""
    if suchmaschine is None:
        return "", []
    if suchmaschine not in SUCHMASCHINEN:
        raise PositionenFehler(f"Unbekannte Suchmaschine: {suchmaschine} ({' | '.join(SUCHMASCHINEN)})")
    quellen = [q for q, m in gsc.SUCHMASCHINE.items() if m == suchmaschine]
    return f" AND quelle IN ({','.join('?' * len(quellen))})", quellen


def bestand(conn: sqlite3.Connection, projekt_id: int, suchmaschine: str | None = None) -> dict | None:
    """Welche Daten liegen vor (optional nur für eine Suchmaschine)? None = noch nichts importiert."""
    sql, werte = _quellen_sql(suchmaschine)
    z = conn.execute("SELECT MIN(datum) von, MAX(datum) bis, COUNT(*) zeilen, GROUP_CONCAT(DISTINCT quelle) quellen,"
                     f" GROUP_CONCAT(DISTINCT land) laender FROM gsc_zeilen WHERE projekt_id = ?{sql}",
                     [projekt_id, *werte]).fetchone()
    if not z["zeilen"]:
        return None
    quellen = sorted(z["quellen"].split(","))
    return {"von": z["von"], "bis": z["bis"], "zeilen": z["zeilen"], "quellen": quellen,
            "suchmaschinen": [m for m in SUCHMASCHINEN if any(gsc.SUCHMASCHINE.get(q) == m for q in quellen)],
            "laender": sorted(l for l in (z["laender"] or "").split(",") if l)}


# ---------- Zeiträume und Filter ----------

def _zeitraeume(conn, projekt_id: int, tage: int, suchmaschine: str = "google") -> dict:
    if not 1 <= tage <= 240:
        raise PositionenFehler("tage muss zwischen 1 und 240 liegen")
    b = bestand(conn, projekt_id, suchmaschine)
    if b is None:
        name = "Search-Console" if suchmaschine == "google" else "Bing"
        raise PositionenFehler(f"Keine {name}-Daten – zuerst importieren")
    bis = date.fromisoformat(b["bis"])
    von = bis - timedelta(days=tage - 1)
    return {"von": von.isoformat(), "bis": bis.isoformat(),
            "vorher_von": (von - timedelta(days=tage)).isoformat(),
            "vorher_bis": (von - timedelta(days=1)).isoformat(), "tage": tage}


def _filter(land: str | None, geraet: str | None, suchmaschine: str = "google") -> tuple[str, list]:
    sql, werte = _quellen_sql(suchmaschine)
    if land:
        sql += " AND land = ?"
        werte.append(land.lower())
    if geraet:
        if geraet.upper() not in GERAETE:
            raise PositionenFehler(f"Unbekanntes Gerät: {geraet} ({' | '.join(GERAETE)})")
        sql += " AND geraet = ?"
        werte.append(geraet.upper())
    return sql, werte


def _pro_begriff(conn, projekt_id: int, von: str, bis: str, f: tuple[str, list]) -> dict[str, dict]:
    """Kennzahlen je Suchbegriff, inklusive Aufteilung auf Seiten."""
    zeilen = conn.execute(
        "SELECT query, seite, SUM(klicks) k, SUM(impressionen) i, SUM(position * impressionen) p"
        f" FROM gsc_zeilen WHERE projekt_id = ? AND datum BETWEEN ? AND ?{f[0]} GROUP BY query, seite",
        [projekt_id, von, bis, *f[1]]).fetchall()
    begriffe: dict[str, dict] = {}
    for z in zeilen:
        b = begriffe.setdefault(z["query"], {"query": z["query"], "klicks": 0, "impressionen": 0, "_p": 0.0,
                                             "seiten": []})
        b["klicks"] += z["k"]
        b["impressionen"] += z["i"]
        b["_p"] += z["p"]
        if z["seite"]:  # Bing liefert keine Seiten
            b["seiten"].append({"seite": z["seite"], "klicks": z["k"], "impressionen": z["i"],
                                "position": round(z["p"] / z["i"], 1)})
    for b in begriffe.values():
        b["position"] = round(b.pop("_p") / b["impressionen"], 1)
        b["ctr"] = round(100 * b["klicks"] / b["impressionen"], 2)
        b["seiten"].sort(key=lambda s: (-s["klicks"], -s["impressionen"]))
    return begriffe


def _sichtbarkeit(positionen: list[float | None]) -> float:
    """Wie Semrush: 100 % = alle Begriffe auf Platz 1. Fehlende Begriffe zählen 0."""
    if not positionen:
        return 0.0
    summe = sum(erwartete_ctr(p) for p in positionen if p is not None)
    return round(100 * summe / (len(positionen) * erwartete_ctr(1)), 1)


def _verteilung(positionen: list[float]) -> dict:
    return {"top3": sum(p <= 3 for p in positionen), "top10": sum(p <= 10 for p in positionen),
            "top20": sum(p <= 20 for p in positionen), "top100": sum(p <= 100 for p in positionen)}


# ---------- Auswertungen ----------

def _auswahl(conn, projekt_id: int, auswahl: str | None, tag: str | None) -> tuple[str, dict, set | None]:
    """Welche Begriffe zählen? Standard: Tracking-Liste, wenn sie nicht leer ist, sonst alle.
    Ein Tag schränkt immer auf die Tracking-Liste ein.
    Rückgabe: (auswahl, getrackte Begriffe → Tags, Filtermenge oder None = keine Einschränkung)."""
    getrackt = {k["query"]: k["tags"] for k in tracking.liste(conn, projekt_id)}
    if tag:
        auswahl = "tracking"
    auswahl = auswahl or ("tracking" if getrackt else "alle")
    if auswahl not in AUSWAHL:
        raise PositionenFehler(f"Unbekannte Auswahl: {auswahl} ({' | '.join(AUSWAHL)})")
    if auswahl == "alle":
        return auswahl, getrackt, None
    return auswahl, getrackt, {k["query"] for k in tracking.liste(conn, projekt_id, tag)}


def keywords(conn: sqlite3.Connection, projekt_id: int, tage: int = 28, land: str | None = None,
             geraet: str | None = None, suche: str | None = None, sortierung: str = "impressionen",
             auswahl: str | None = None, tag: str | None = None, suchmaschine: str = "google") -> dict:
    """Suchbegriffe mit Position jetzt/vorher, Klicks, Impressionen, CTR und Seiten.
    auswahl: tracking (nur Tracking-Liste) | alle (alle aus der Search Console); tag: nur Begriffe mit diesem Tag."""
    projekte.holen(conn, projekt_id)
    zr = _zeitraeume(conn, projekt_id, tage, suchmaschine)
    f = _filter(land, geraet, suchmaschine)
    auswahl, getrackt, nur = _auswahl(conn, projekt_id, auswahl, tag)
    jetzt = _pro_begriff(conn, projekt_id, zr["von"], zr["bis"], f)
    vorher = _pro_begriff(conn, projekt_id, zr["vorher_von"], zr["vorher_bis"], f)
    liste = []
    for query in (nur if nur is not None else jetzt.keys() | vorher.keys()):
        j, v = jetzt.get(query), vorher.get(query)
        basis = j or {"klicks": 0, "impressionen": 0, "ctr": 0.0, "position": None, "seiten": []}
        pos_v = v["position"] if v else None
        liste.append({
            "query": query, "klicks": basis["klicks"], "impressionen": basis["impressionen"], "ctr": basis["ctr"],
            "position": basis["position"], "position_vorher": pos_v,
            # positiv = besser geworden (Position kleiner)
            "aenderung": round(pos_v - basis["position"], 1) if j and v else None,
            "status": "keine Daten" if not j and not v else "neu" if not v else "verloren" if not j else "",
            "klicks_vorher": v["klicks"] if v else 0,
            "beste_seite": basis["seiten"][0]["seite"] if basis["seiten"] else None,
            "seiten": basis["seiten"],
            "getrackt": query in getrackt, "tags": getrackt.get(query, []),
        })
    if suche:
        liste = [k for k in liste if suche.lower() in k["query"].lower()]
    schluessel = {
        "impressionen": lambda k: -k["impressionen"], "klicks": lambda k: -k["klicks"],
        "position": lambda k: k["position"] if k["position"] is not None else 999,
        "aenderung": lambda k: -(k["aenderung"] or 0), "query": lambda k: k["query"],
    }
    if sortierung not in schluessel:
        raise PositionenFehler(f"Unbekannte Sortierung: {sortierung} ({' | '.join(schluessel)})")
    liste.sort(key=schluessel[sortierung])
    return {"zeitraum": zr, "auswahl": auswahl, "tag": tag, "keywords": liste}


def uebersicht(conn: sqlite3.Connection, projekt_id: int, tage: int = 28, land: str | None = None,
               geraet: str | None = None, auswahl: str | None = None, tag: str | None = None,
               suchmaschine: str = "google") -> dict:
    """Kennzahlen wie in Semrush Position Tracking: Sichtbarkeit, Ø-Position, Verteilung,
    Gewinner/Verlierer, Striking Distance, Kannibalisierung, Tagesverlauf.
    Mit Tracking-Liste zählen nur deren Begriffe (siehe keywords)."""
    k = keywords(conn, projekt_id, tage, land, geraet, auswahl=auswahl, tag=tag, suchmaschine=suchmaschine)
    zr, liste = k["zeitraum"], k["keywords"]
    jetzt = [x["position"] for x in liste if x["position"] is not None]
    vorher = [x["position_vorher"] for x in liste if x["position_vorher"] is not None]

    def summe(feld):
        return sum(x[feld] for x in liste)

    impressionen = summe("impressionen")
    mit_aenderung = [x for x in liste if x["aenderung"] is not None and abs(x["aenderung"]) >= 1]
    return {
        "zeitraum": zr, "auswahl": k["auswahl"], "tag": tag, "suchmaschine": suchmaschine,
        "bestand": bestand(conn, projekt_id, suchmaschine),
        "kennzahlen": {
            "keywords": len(jetzt), "gezaehlt": len(liste), "keywords_vorher": len(vorher),
            "klicks": summe("klicks"), "klicks_vorher": summe("klicks_vorher"),
            "impressionen": impressionen,
            "ctr": round(100 * summe("klicks") / impressionen, 2) if impressionen else 0.0,
            "position": round(sum(jetzt) / len(jetzt), 1) if jetzt else None,
            "position_vorher": round(sum(vorher) / len(vorher), 1) if vorher else None,
            "sichtbarkeit": _sichtbarkeit([x["position"] for x in liste]),
            "sichtbarkeit_vorher": _sichtbarkeit([x["position_vorher"] for x in liste]),
        },
        "verteilung": _verteilung(jetzt),
        "verteilung_vorher": _verteilung(vorher),
        "gewinner": sorted([x for x in mit_aenderung if x["aenderung"] > 0], key=lambda x: -x["aenderung"])[:10],
        "verlierer": sorted([x for x in mit_aenderung if x["aenderung"] < 0], key=lambda x: x["aenderung"])[:10],
        "neu": [x["query"] for x in liste if x["status"] == "neu"],
        "verloren": [x["query"] for x in liste if x["status"] == "verloren"],
        "striking": sorted([x for x in liste if x["position"] and STRIKING[0] <= x["position"] <= STRIKING[1]],
                           key=lambda x: -x["impressionen"]),
        "kannibalisierung": _kannibalisierung(liste),
        "tage": _tagesverlauf(conn, projekt_id, zr["von"], zr["bis"], _filter(land, geraet, suchmaschine),
                              [x["query"] for x in liste] if k["auswahl"] == "tracking" else None),
    }


def _kannibalisierung(liste: list[dict]) -> list[dict]:
    """Begriffe, bei denen mehrere eigene Seiten nennenswert Impressionen bekommen."""
    treffer = []
    for x in liste:
        if not x["impressionen"]:
            continue
        seiten = [dict(s, anteil=round(100 * s["impressionen"] / x["impressionen"]))
                  for s in x["seiten"] if s["impressionen"] / x["impressionen"] >= KANNIBAL_ANTEIL]
        if len(seiten) >= 2:
            treffer.append({"query": x["query"], "impressionen": x["impressionen"], "position": x["position"],
                            "seiten": seiten})
    return sorted(treffer, key=lambda t: -t["impressionen"])


def _tagesverlauf(conn, projekt_id: int, von: str, bis: str, f: tuple[str, list],
                  queries: list[str] | None = None) -> list[dict]:
    sql, werte = f
    if queries is not None:
        sql += f" AND query IN ({','.join('?' * len(queries))})"
        werte = [*werte, *queries]
    zeilen = conn.execute(
        "SELECT datum, SUM(klicks) k, SUM(impressionen) i, SUM(position * impressionen) p"
        f" FROM gsc_zeilen WHERE projekt_id = ? AND datum BETWEEN ? AND ?{sql} GROUP BY datum ORDER BY datum",
        [projekt_id, von, bis, *werte]).fetchall()
    return [{"datum": z["datum"], "klicks": z["k"], "impressionen": z["i"], "position": round(z["p"] / z["i"], 1)}
            for z in zeilen]


def keyword_verlauf(conn: sqlite3.Connection, projekt_id: int, query: str, tage: int = 90,
                    land: str | None = None, geraet: str | None = None, suchmaschine: str = "google") -> dict:
    """Tageswerte eines Suchbegriffs, gesamt und je Seite (für Diagramm und Kannibalisierung)."""
    projekte.holen(conn, projekt_id)
    zr = _zeitraeume(conn, projekt_id, tage, suchmaschine)
    f = _filter(land, geraet, suchmaschine)
    zeilen = conn.execute(
        "SELECT datum, seite, SUM(klicks) k, SUM(impressionen) i, SUM(position * impressionen) p"
        f" FROM gsc_zeilen WHERE projekt_id = ? AND query = ? AND datum BETWEEN ? AND ?{f[0]}"
        " GROUP BY datum, seite ORDER BY datum",
        [projekt_id, query, zr["von"], zr["bis"], *f[1]]).fetchall()
    if not zeilen:
        raise PositionenFehler(f"Suchbegriff {query!r} nicht gefunden")
    tage_gesamt: dict[str, dict] = {}
    seiten: dict[str, list] = {}
    for z in zeilen:
        t = tage_gesamt.setdefault(z["datum"], {"datum": z["datum"], "klicks": 0, "impressionen": 0, "_p": 0.0})
        t["klicks"] += z["k"]
        t["impressionen"] += z["i"]
        t["_p"] += z["p"]
        seiten.setdefault(z["seite"], []).append({"datum": z["datum"], "position": round(z["p"] / z["i"], 1),
                                                  "impressionen": z["i"]})
    for t in tage_gesamt.values():
        t["position"] = round(t.pop("_p") / t["impressionen"], 1)
    return {"query": query, "zeitraum": zr, "tage": list(tage_gesamt.values()), "seiten": seiten}
