"""Service: CSV-Export von Issues und gecrawlten Seiten.

Format für deutsches Excel: Semikolon als Trenner, UTF-8 mit BOM.
"""

import csv
import io
import sqlite3

from app import checks
from app.core import keywords, positionen
from app.core.audit import crawl_holen
from app.gsc.laender import land_name

SEITEN_SPALTEN = ("url", "status_code", "tiefe", "title", "meta_description", "h1_text", "woerter",
                  "ladezeit_ms", "html_bytes", "canonical", "meta_robots", "lang", "blockiert", "link_rank")


def _csv(kopf: list[str], zeilen) -> str:
    puffer = io.StringIO()
    puffer.write("﻿")
    schreiber = csv.writer(puffer, delimiter=";", lineterminator="\r\n")
    schreiber.writerow(kopf)
    schreiber.writerows(zeilen)
    return puffer.getvalue()


def issues_csv(conn: sqlite3.Connection, crawl_id: int) -> str:
    """Ein Treffer pro Zeile: Schweregrad, Kategorie, Check, URL, Detail."""
    crawl_holen(conn, crawl_id)
    rang = {s: n for n, s in enumerate(checks.SCHWEREGRADE)}
    zeilen = []
    for check_id, url, detail in conn.execute("""
            SELECT i.check_id, s.url, i.detail FROM issues i LEFT JOIN seiten s ON s.id = i.seite_id
            WHERE i.crawl_id=? ORDER BY i.check_id, s.url""", (crawl_id,)):
        c = checks.REGISTER.get(check_id)
        if c:
            zeilen.append((c.schwere, checks.KATEGORIEN[c.kategorie], c.name, check_id, url or "ganze Website", detail or ""))
    zeilen.sort(key=lambda z: rang[z[0]])
    return _csv(["Schweregrad", "Kategorie", "Problem", "Check-ID", "URL", "Detail"], zeilen)


def seiten_csv(conn: sqlite3.Connection, crawl_id: int) -> str:
    """Alle gecrawlten Seiten mit den wichtigsten Messwerten und Anzahl Issues."""
    crawl_holen(conn, crawl_id)
    spalten = ", ".join(f"s.{s}" for s in SEITEN_SPALTEN)
    zeilen = conn.execute(f"""
        SELECT {spalten}, COUNT(i.id) FROM seiten s LEFT JOIN issues i ON i.seite_id = s.id
        WHERE s.crawl_id=? GROUP BY s.id ORDER BY s.tiefe, s.url""", (crawl_id,)).fetchall()
    return _csv([*SEITEN_SPALTEN, "issues"], [tuple("" if v is None else v for v in z) for z in zeilen])


def _zahl(wert: float | None) -> str:
    """Dezimalkomma für deutsches Excel, leer bei fehlendem Wert."""
    return "" if wert is None else f"{wert:g}".replace(".", ",")


def keywords_csv(conn: sqlite3.Connection, projekt_id: int, tage: int = 28, land: str | None = None,
                 geraet: str | None = None, auswahl: str | None = None, tag: str | None = None,
                 suche: str | None = None, sortierung: str = "impressionen", suchmaschine: str = "google") -> str:
    """Suchbegriffe wie in der Tabelle „Positionen“ (gleiche Filter), ein Begriff pro Zeile."""
    k = positionen.keywords(conn, projekt_id, tage, land, geraet, suche, sortierung, auswahl, tag, suchmaschine)
    zr = k["zeitraum"]
    filter_text = ", ".join(t for t in [
        "Bing" if suchmaschine == "bing" else "Google",
        f"{zr['von']} bis {zr['bis']} (vorher {zr['vorher_von']} bis {zr['vorher_bis']})",
        land_name(land) if land else "", geraet or "",
        "Tracking-Liste" if k["auswahl"] == "tracking" else "alle Suchbegriffe", f"Tag {tag}" if tag else "",
    ] if t)
    zeilen = [(x["query"], _zahl(x["position"]), _zahl(x["position_vorher"]), _zahl(x["aenderung"]),
               x["klicks"], x["klicks_vorher"], x["impressionen"], _zahl(x["ctr"]), x["beste_seite"] or "",
               len(x["seiten"]), "ja" if x["getrackt"] else "", ", ".join(x["tags"]), x["status"], filter_text)
              for x in k["keywords"]]
    return _csv(["Suchbegriff", "Position", "Position vorher", "Änderung (+ = besser)", "Klicks", "Klicks vorher",
                 "Impressionen", "CTR %", "Beste Seite", "Seiten", "Getrackt", "Tags", "Status", "Zeitraum/Filter"],
                zeilen)


def recherche_csv(conn: sqlite3.Connection, recherche_id: int, **filter) -> str:
    """Ideen einer Keyword-Recherche (gleiche Filter wie die Tabelle), alle Treffer ohne Seitenbegrenzung."""
    d = keywords.ideen(conn, recherche_id, limit=100_000, **filter)
    zeilen = [(i["keyword"], i["intent"], i["gruppe"], i["woerter"], "ja" if i["frage"] else "",
               ", ".join(i["quellen"]), "" if i["gsc_impressionen"] is None else i["gsc_impressionen"],
               "" if i["gsc_klicks"] is None else i["gsc_klicks"], _zahl(i["gsc_position"])) for i in d["ideen"]]
    return _csv(["Keyword", "Intent", "Gruppe", "Wörter", "Frage", "Quellen", "Eigene Impressionen (90 T.)",
                 "Eigene Klicks (90 T.)", "Eigene Position"], zeilen)
