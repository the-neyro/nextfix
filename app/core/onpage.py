"""Service: On-Page SEO Checker (wie Semrush, aber ohne SERP-Abfragen).

Eine Seite wird gegen ein Keyword geprüft: Title, H1, Text, URL, Technik, interne Links (aus dem letzten Crawl),
Core Web Vitals (falls gemessen). Dazu semantische Ideen: Begriffe und Fragen aus Google Suggest (gecacht),
Begriffe, die bis zu 3 selbst gewählte Mitbewerber-Seiten nutzen. Die Google-Top-10 werden nicht abgefragt (ToS).
"""

import json
import sqlite3
import statistics

import httpx

from app.core import audit, projekte
from app.crawler.urls import normalisieren
from app.keywords.suggest import MODIFIKATOREN, W_FRAGEN, Suggest, SuggestFehler
from app.onpage import abgleich, ki, semantik
from app.onpage.seite import lesen

MAX_MITBEWERBER = 3
TIMEOUT_S = 20

# austauschbar für Tests
SUGGEST_FABRIK = Suggest


class OnpageFehler(ValueError):
    """Ungültige Eingabe oder Seite nicht abrufbar."""


def abrufen(url: str, user_agent: str) -> tuple[int, str, str]:
    """(Status, HTML, endgültige URL nach Weiterleitungen)."""
    try:
        r = httpx.get(url, headers={"User-Agent": user_agent}, follow_redirects=True, timeout=TIMEOUT_S)
    except httpx.HTTPError as e:
        raise OnpageFehler(f"{url} nicht erreichbar ({type(e).__name__})") from None
    if "html" not in r.headers.get("content-type", "html"):
        raise OnpageFehler(f"{url} ist keine HTML-Seite")
    return r.status_code, r.text, str(r.url)


# austauschbar für Tests
HOLER = abrufen


def _eingaben(url: str, keyword: str, mitbewerber: list[str]) -> tuple[str, str, list[str]]:
    url = normalisieren(url.strip(), url.strip()) or ""
    if not url.startswith(("http://", "https://")):
        raise OnpageFehler("URL muss mit http:// oder https:// beginnen")
    keyword = " ".join((keyword or "").split()).lower()
    if not 2 <= len(keyword) <= 80:
        raise OnpageFehler("Keyword muss 2 bis 80 Zeichen lang sein")
    mitbewerber = [m.strip() for m in mitbewerber if m and m.strip()]
    if len(mitbewerber) > MAX_MITBEWERBER:
        raise OnpageFehler(f"Höchstens {MAX_MITBEWERBER} Mitbewerber-URLs")
    if any(not m.startswith(("http://", "https://")) for m in mitbewerber):
        raise OnpageFehler("Mitbewerber-URLs müssen mit http:// oder https:// beginnen")
    return url, keyword, mitbewerber


def _aus_crawl(conn, projekt_id: int, url: str, keyword: str) -> tuple[dict | None, dict | None]:
    """Eingehende interne Links (letzter Crawl) und letzte mobile Vitals-Messung der Seite."""
    crawl_id = audit.letzter_crawl_id(conn, projekt_id)
    eingehend = None
    if crawl_id and conn.execute("SELECT 1 FROM seiten WHERE crawl_id = ? AND url = ?", (crawl_id, url)).fetchone():
        anker = [z["anker_text"] or "" for z in conn.execute(
            "SELECT anker_text FROM links WHERE crawl_id = ? AND ziel_url = ? AND art = 'a' AND intern = 1",
            (crawl_id, url))]
        eingehend = {"links": len(anker), "mit_keyword": sum(abgleich.woerter_in(keyword, a) for a in anker if a)}
    v = conn.execute(
        "SELECT v.lcp, v.cls, v.tbt FROM vitals v JOIN vitals_laeufe l ON l.id = v.lauf_id JOIN crawls c ON c.id = l.crawl_id"
        " WHERE c.projekt_id = ? AND v.url = ? AND v.geraet = 'mobile' AND v.fehler IS NULL ORDER BY l.id DESC LIMIT 1",
        (projekt_id, url)).fetchone()
    return eingehend, (dict(v) if v else None)


def _suggest(conn, keyword: str) -> tuple[list[str], set[str], str | None]:
    """Vorschläge zum Keyword: pur, W-Fragen davor, typische Zusätze dahinter (max. 21 Anfragen, 30 Tage Cache).
    Zusätzlich die Wörter, die wir selbst angehängt haben und die bei der puren Anfrage nicht vorkamen
    (die sollen nicht als „verwandte Begriffe“ zählen)."""
    s = SUGGEST_FABRIK(conn, "de", "de")
    vorschlaege: list[str] = []
    eigene_zusaetze = {abgleich.norm(w) for t in W_FRAGEN + MODIFIKATOREN for w in t.split()}
    try:
        pur = s.vorschlaege(keyword)
        vorschlaege += pur
        eigene_zusaetze -= {w for v in pur for w in abgleich.norm(v).split()}
        for anfrage in [f"{w} {keyword}" for w in W_FRAGEN] + [f"{keyword} {m}" for m in MODIFIKATOREN]:
            vorschlaege += s.vorschlaege(anfrage)
    except SuggestFehler as e:
        return vorschlaege, eigene_zusaetze, str(e)
    return list(dict.fromkeys(vorschlaege)), eigene_zusaetze, None


def pruefen(conn: sqlite3.Connection, projekt_id: int, url: str, keyword: str,
            mitbewerber: list[str] | None = None, mit_suggest: bool = True) -> dict:
    projekte.holen(conn, projekt_id)
    url, keyword, mitbewerber = _eingaben(url, keyword, mitbewerber or [])
    ua = audit.einstellungen_holen(conn, projekt_id)["user_agent"]
    status, html, end_url = HOLER(url, ua)
    seite = lesen(html, end_url, status)
    hinweise = []
    if normalisieren(end_url, end_url) != url:
        hinweise.append(f"Weiterleitung auf {end_url} – geprüft wurde die Zielseite.")

    mb = []
    for m in mitbewerber:
        try:
            st, h, ziel = HOLER(m, ua)
            s_m = lesen(h, ziel, st)
            mb.append({"url": ziel, "status": st, "woerter": s_m.woerter, "title": s_m.title, "_text": s_m.text})
        except OnpageFehler as e:
            mb.append({"url": m, "fehler": str(e)})
    mb_ok = [m for m in mb if "fehler" not in m and m["status"] == 200]
    mb_woerter = round(statistics.median(m["woerter"] for m in mb_ok)) if mb_ok else None

    eingehend, vitals = _aus_crawl(conn, projekt_id, normalisieren(end_url, end_url), keyword)
    if eingehend is None:
        hinweise.append("Seite ist nicht im letzten Crawl – interne Links nicht bewertet.")
    pruefungen = abgleich.pruefen(seite, keyword, eingehend, vitals, mb_woerter)

    vorschlaege, zusaetze, suggest_fehler = _suggest(conn, keyword) if mit_suggest else ([], set(), None)
    if suggest_fehler:
        hinweise.append(suggest_fehler)
    begriffe = semantik.aus_suggest(vorschlaege, keyword, seite.text + " " + " ".join(seite.zwischen), zusaetze)
    if begriffe:
        anteil = sum(b["auf_seite"] for b in begriffe) / len(begriffe)
        fehlend = [b["begriff"] for b in begriffe if not b["auf_seite"]]
        pruefungen.append(abgleich.Pruefung(
            "verwandte_begriffe", "Semantik", "Verwandte Suchbegriffe abgedeckt (≥ 50 %)", 2, anteil >= 0.5,
            f"{round(100 * anteil)} % der {len(begriffe)} Begriffe auf der Seite",
            "" if anteil >= 0.5 else "Diese Begriffe sinnvoll einbauen: " + ", ".join(fehlend[:8])))
    fragen = semantik.fragen(vorschlaege, seite.text, seite.zwischen, keyword)
    mb_begriffe = semantik.aus_mitbewerbern([m["_text"] for m in mb_ok], keyword, seite.text)

    ideen = sorted((x for x in pruefungen if x.ok is False), key=lambda x: (-x.gewicht, x.kategorie))
    ergebnis = {
        "url": url, "end_url": end_url, "keyword": keyword, "score": abgleich.score(pruefungen),
        "seite": {"status": status, "title": seite.title, "h1": seite.h1, "woerter": seite.woerter,
                  "zwischen": len(seite.zwischen), "bilder": seite.bilder},
        "pruefungen": [x.als_dict() for x in pruefungen],
        "ki": ki.bewerten(seite),
        "ideen": [{"kategorie": x.kategorie, "prioritaet": {3: "hoch", 2: "mittel"}.get(x.gewicht, "niedrig"),
                   "titel": x.titel, "tipp": x.tipp, "detail": x.detail, "vorschlag": x.vorschlag} for x in ideen],
        "begriffe_suggest": begriffe, "fragen": fragen, "begriffe_mitbewerber": mb_begriffe,
        "mitbewerber": [{k: v for k, v in m.items() if k != "_text"} for m in mb],
        "hinweise": hinweise,
    }
    pid = conn.execute("INSERT INTO onpage_pruefungen (projekt_id, url, keyword, score, ergebnis) VALUES (?, ?, ?, ?, ?)",
                       (projekt_id, url, keyword, ergebnis["score"], json.dumps(ergebnis, ensure_ascii=False))).lastrowid
    conn.commit()
    return {"id": pid, **ergebnis}


def holen(conn: sqlite3.Connection, pruefung_id: int) -> dict:
    z = conn.execute("SELECT * FROM onpage_pruefungen WHERE id = ?", (pruefung_id,)).fetchone()
    if z is None:
        raise OnpageFehler(f"Prüfung {pruefung_id} nicht gefunden")
    return {"id": z["id"], "projekt_id": z["projekt_id"], "angelegt_am": z["angelegt_am"], **json.loads(z["ergebnis"])}


def liste(conn: sqlite3.Connection, projekt_id: int) -> list[dict]:
    projekte.holen(conn, projekt_id)
    return [dict(z) for z in conn.execute(
        "SELECT id, url, keyword, score, angelegt_am FROM onpage_pruefungen WHERE projekt_id = ? ORDER BY id DESC",
        (projekt_id,))]
