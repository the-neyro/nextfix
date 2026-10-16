"""Service: Thematische Berichte je Kategorie – Health, Issues und Kennzahlen (Verteilungen).

Jede Kennzahl ist {"titel", "zeilen": [{"label", "wert"}]}, damit UI, API und MCP sie einheitlich anzeigen.
"""

import sqlite3
from collections import Counter
from collections.abc import Callable

from app import checks
from app.checks.katalog import HTML, fakten, json_spalte
from app.core import audit

Kennzahl = dict


def _kennzahl(titel: str, zeilen) -> Kennzahl:
    return {"titel": titel, "zeilen": [{"label": str(label), "wert": wert} for label, wert in zeilen]}


def _gruppen(conn, crawl_id: int, titel: str, ausdruck: str, gruppen: list[str], bedingung: str = HTML) -> Kennzahl:
    """Zählt Seiten je Gruppe; ausdruck liefert den Gruppennamen (SQL CASE), Reihenfolge aus gruppen."""
    zahlen = dict(conn.execute(
        f"SELECT {ausdruck} AS g, COUNT(*) FROM seiten WHERE crawl_id=? AND {bedingung} GROUP BY g", (crawl_id,)))
    return _kennzahl(titel, [(g, zahlen.get(g, 0)) for g in gruppen])


# ---------- je Thema ----------

def _crawlbarkeit(conn, crawl_id):
    return [
        _gruppen(conn, crawl_id, "Seiten nach Klicktiefe",
                 "CASE WHEN tiefe >= 4 THEN '4+' ELSE CAST(tiefe AS TEXT) END", ["0", "1", "2", "3", "4+"], "1"),
        _gruppen(conn, crawl_id, "Seiten nach Status", """CASE
            WHEN blockiert = 1 THEN 'blockiert (robots.txt)' WHEN status_code IS NULL THEN 'nicht erreichbar'
            WHEN status_code < 300 THEN '2xx' WHEN status_code < 400 THEN '3xx Weiterleitung'
            WHEN status_code < 500 THEN '4xx' ELSE '5xx' END""",
                 ["2xx", "3xx Weiterleitung", "4xx", "5xx", "nicht erreichbar", "blockiert (robots.txt)"], "1"),
    ]


def _https(conn, crawl_id):
    f = fakten(conn, crawl_id)
    tls, umleitung = f.get("tls") or {}, f.get("http_zu_https") or {}
    grundlagen = [
        ("Zertifikat gültig bis", f"{tls['ablauf']} (noch {tls['rest_tage']} Tage)" if tls.get("ablauf") else "–"),
        ("Protokoll", tls.get("protokoll") or "–"),
        ("HTTP leitet auf HTTPS um", "ja" if umleitung.get("ok") else "nein" if umleitung else "–"),
    ]
    return [
        _kennzahl("HTTPS-Grundlagen", grundlagen),
        _gruppen(conn, crawl_id, "Seiten nach Protokoll",
                 "CASE WHEN url LIKE 'https://%' THEN 'HTTPS' ELSE 'HTTP' END", ["HTTPS", "HTTP"], "1"),
    ]


def _links(conn, crawl_id):
    eingehend = """(SELECT COUNT(DISTINCT l.seite_id) FROM links l
                    WHERE l.crawl_id = seiten.crawl_id AND l.ziel_url = seiten.url AND l.art = 'a' AND l.intern = 1)"""
    return [
        _gruppen(conn, crawl_id, "Seiten nach interner Link-Stärke (0–100)", """CASE
            WHEN link_rank < 10 THEN '0–9' WHEN link_rank < 30 THEN '10–29' WHEN link_rank < 60 THEN '30–59'
            WHEN link_rank < 90 THEN '60–89' ELSE '90–100' END""",
                 ["0–9", "10–29", "30–59", "60–89", "90–100"], f"{HTML} AND link_rank IS NOT NULL"),
        _gruppen(conn, crawl_id, "Seiten nach eingehenden internen Links", f"""CASE
            WHEN {eingehend} = 0 THEN '0' WHEN {eingehend} = 1 THEN '1' WHEN {eingehend} <= 5 THEN '2–5'
            WHEN {eingehend} <= 20 THEN '6–20' ELSE 'über 20' END""", ["0", "1", "2–5", "6–20", "über 20"]),
    ]


def _international(conn, crawl_id):
    mit = len(json_spalte(conn, crawl_id, "hreflang", "hreflang != '[]'"))
    gesamt = conn.execute(f"SELECT COUNT(*) FROM seiten WHERE crawl_id=? AND {HTML}", (crawl_id,)).fetchone()[0]
    sprachen = conn.execute(
        f"SELECT COALESCE(lang, 'ohne lang'), COUNT(*) FROM seiten WHERE crawl_id=? AND {HTML} GROUP BY 1 ORDER BY 2 DESC LIMIT 8",
        (crawl_id,)).fetchall()
    return [
        _kennzahl("hreflang", [("Seiten mit hreflang", mit), ("Seiten ohne hreflang", gesamt - mit)]),
        _kennzahl("Sprachen (lang-Attribut)", sprachen),
    ]


def _technik(conn, crawl_id):
    typen, mit, fehlerhaft = Counter(), 0, 0
    for _, _, m in json_spalte(conn, crawl_id, "markup"):
        if m.get("typen"):
            mit += 1
            typen.update(set(m["typen"]))
        fehlerhaft += bool(m.get("fehler"))
    gesamt = conn.execute(f"SELECT COUNT(*) FROM seiten WHERE crawl_id=? AND {HTML}", (crawl_id,)).fetchone()[0]
    return [
        _kennzahl("Strukturierte Daten", [("Seiten mit Markup", mit), ("Seiten ohne Markup", gesamt - mit),
                                          ("Seiten mit fehlerhaftem Markup", fehlerhaft)]),
        _kennzahl("Häufigste schema.org-Typen", typen.most_common(10)),
    ]


def _performance(conn, crawl_id):
    return [
        _gruppen(conn, crawl_id, "Antwortzeit HTML", """CASE
            WHEN ladezeit_ms < 300 THEN 'unter 0,3 s' WHEN ladezeit_ms < 1000 THEN '0,3–1 s'
            WHEN ladezeit_ms < 3000 THEN '1–3 s' ELSE 'über 3 s' END""",
                 ["unter 0,3 s", "0,3–1 s", "1–3 s", "über 3 s"], "status_code = 200 AND ladezeit_ms IS NOT NULL"),
        _gruppen(conn, crawl_id, "HTML-Größe", """CASE
            WHEN html_bytes < 50000 THEN 'unter 50 KB' WHEN html_bytes < 200000 THEN '50–200 KB'
            WHEN html_bytes < 1000000 THEN '200 KB – 1 MB' ELSE 'über 1 MB' END""",
                 ["unter 50 KB", "50–200 KB", "200 KB – 1 MB", "über 1 MB"], f"{HTML} AND html_bytes IS NOT NULL"),
    ]


def _ki(conn, crawl_id):
    llms = fakten(conn, crawl_id).get("llms") or {}
    llms_text = "vorhanden" if llms.get("status") == 200 else "fehlt" if llms else "–"
    if llms.get("status") == 200 and not llms.get("format_ok"):
        llms_text = "vorhanden, mit Formatfehlern"
    semantik = json_spalte(conn, crawl_id, "semantik")
    mit_haupt = sum(1 for _, _, t in semantik if "main" in t or "article" in t)
    lesbar = json_spalte(conn, crawl_id, "lesbarkeit")
    geo = [g for *_, g in json_spalte(conn, crawl_id, "geo")]
    return [
        _kennzahl("Für KI-Crawler", [("llms.txt", llms_text), ("Links in llms.txt", llms.get("links_anzahl", "–"))]),
        _kennzahl("Antwort-Signale", [("Seiten mit Zahlen/Statistiken", sum(1 for g in geo if g.get("zahlen"))),
                                      ("Seiten mit externen Quellen", sum(1 for g in geo if g.get("quellen"))),
                                      ("Seiten mit Fragen als Überschrift", sum(1 for g in geo if g.get("fragen")))]),
        _kennzahl("Struktur", [("Seiten mit <main>/<article>", mit_haupt), ("Seiten ohne", len(semantik) - mit_haupt)]),
        _kennzahl("Lesbarkeit", [("ohne Auffälligkeiten", sum(1 for *_, p in lesbar if not p)),
                                 ("mit Auffälligkeiten", sum(1 for *_, p in lesbar if p))]),
    ]


def _inhalt(conn, crawl_id):
    return [
        _gruppen(conn, crawl_id, "Wörter pro Seite", """CASE
            WHEN woerter < 200 THEN 'unter 200' WHEN woerter < 500 THEN '200–499'
            WHEN woerter < 1000 THEN '500–999' ELSE 'ab 1000' END""", ["unter 200", "200–499", "500–999", "ab 1000"]),
        _gruppen(conn, crawl_id, "Title-Länge (Zeichen)", """CASE
            WHEN COALESCE(title, '') = '' THEN 'fehlt' WHEN LENGTH(title) <= 10 THEN '1–10'
            WHEN LENGTH(title) <= 70 THEN '11–70' ELSE 'über 70' END""", ["fehlt", "1–10", "11–70", "über 70"]),
    ]


KENNZAHLEN: dict[str, Callable[[sqlite3.Connection, int], list[Kennzahl]]] = {
    "crawlbarkeit": _crawlbarkeit, "https": _https, "links": _links, "inhalt": _inhalt,
    "performance": _performance, "technik": _technik, "international": _international, "ki": _ki,
}


def thema(conn: sqlite3.Connection, crawl_id: int, kategorie: str) -> dict:
    """Thematischer Bericht: Health der Kategorie, ihre Issues und Kennzahlen."""
    if kategorie not in checks.KATEGORIEN:
        raise audit.AuditFehler(f"Unbekanntes Thema: {kategorie} ({', '.join(checks.KATEGORIEN)})")
    audit.crawl_holen(conn, crawl_id)
    return {
        "id": kategorie,
        "name": checks.KATEGORIEN[kategorie],
        "health": audit._health(conn, crawl_id, kategorie),
        "issues": audit.issues_liste(conn, crawl_id, kategorie=kategorie),
        "kennzahlen": KENNZAHLEN[kategorie](conn, crawl_id),
    }
