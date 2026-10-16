"""Service: Site Audit – Einstellungen, Crawls starten/stoppen, Ergebnisse auswerten."""

import socket
import sqlite3
import threading
from contextlib import closing
from urllib.parse import urlsplit

from app import checks
from app.core import ausblenden, autoritaet, linkrank, projekte, score
from app.crawler.crawler import CrawlEinstellungen, Crawler
from app.crawler.filter import liste
from app.db import verbinden


class AuditFehler(ValueError):
    """Ungültige Eingabe oder unpassender Zustand."""


CRAWLER_FELDER = ("start_url", "seitenlimit", "crawl_delay", "user_agent", "robots_beachten", "quelle",
                  "erlauben", "sperren", "parameter_entfernen", "js_rendern")
EINSTELLUNGS_FELDER = (*CRAWLER_FELDER, "checks_aus", "ladezeit_auto")
LISTEN_FELDER = ("erlauben", "sperren", "parameter_entfernen", "checks_aus")

# ---------- Einstellungen ----------

def einstellungen_holen(conn: sqlite3.Connection, projekt_id: int) -> dict:
    p = projekte.holen(conn, projekt_id)
    conn.execute("INSERT OR IGNORE INTO einstellungen (projekt_id) VALUES (?)", (projekt_id,))
    conn.commit()
    z = dict(conn.execute("SELECT * FROM einstellungen WHERE projekt_id=?", (projekt_id,)).fetchone())
    z["start_url"] = z["start_url"] or f"https://{p.domain}/"
    z["robots_beachten"] = bool(z["robots_beachten"])
    z["ladezeit_auto"] = bool(z["ladezeit_auto"])
    z["js_rendern"] = bool(z["js_rendern"])
    return z


def einstellungen_setzen(conn: sqlite3.Connection, projekt_id: int, **werte) -> dict:
    einstellungen_holen(conn, projekt_id)
    unbekannt = set(werte) - set(EINSTELLUNGS_FELDER)
    if unbekannt:
        raise AuditFehler(f"Unbekannte Einstellung(en): {', '.join(sorted(unbekannt))}")
    werte = {k: v for k, v in werte.items() if v is not None}
    if "start_url" in werte and not str(werte["start_url"]).startswith(("http://", "https://")):
        raise AuditFehler("start_url muss mit http:// oder https:// beginnen")
    if "seitenlimit" in werte and not 1 <= int(werte["seitenlimit"]) <= 100_000:
        raise AuditFehler("seitenlimit muss zwischen 1 und 100000 liegen")
    if "crawl_delay" in werte and not 0 <= float(werte["crawl_delay"]) <= 30:
        raise AuditFehler("crawl_delay muss zwischen 0 und 30 Sekunden liegen")
    if "quelle" in werte and werte["quelle"] not in ("website", "sitemap", "beides"):
        raise AuditFehler("quelle muss 'website', 'sitemap' oder 'beides' sein")
    for feld in ("robots_beachten", "ladezeit_auto", "js_rendern"):
        if feld in werte:
            werte[feld] = int(bool(werte[feld]))
    for feld in LISTEN_FELDER:
        if feld in werte:  # Listen einheitlich speichern: ein Eintrag pro Zeile
            eintraege = werte[feld] if isinstance(werte[feld], list) else liste(werte[feld])
            werte[feld] = "\n".join(e.strip() for e in eintraege if e.strip())
    unbekannte_checks = set(liste(werte.get("checks_aus"))) - set(checks.REGISTER)
    if unbekannte_checks:
        raise AuditFehler(f"Unbekannte Check-ID(s): {', '.join(sorted(unbekannte_checks))}")
    for feld, wert in werte.items():
        conn.execute(f"UPDATE einstellungen SET {feld}=? WHERE projekt_id=?", (wert, projekt_id))
    conn.commit()
    return einstellungen_holen(conn, projekt_id)


# ---------- Crawls ----------

# Ohne Lebenszeichen so lange gilt ein Crawl als tot (Prozess beendet, z. B. Server-Neustart).
# Muss größer sein als Timeout (15 s) + maximale Pause (30 s).
VERWAIST_NACH_SEKUNDEN = 120


def _ist_verwaist(conn: sqlite3.Connection, crawl_id: int) -> bool:
    z = conn.execute("""
        SELECT status = 'laeuft' AND (julianday('now') - julianday(COALESCE(lebenszeichen, gestartet_am))) * 86400 > ?
        FROM crawls WHERE id=?""", (VERWAIST_NACH_SEKUNDEN, crawl_id)).fetchone()
    return bool(z and z[0])


def server_ip(url: str) -> str | None:
    """IP des Webservers (None, wenn nicht auflösbar). Mehrere Domains teilen sich oft einen Server."""
    try:
        return socket.gethostbyname(urlsplit(url).hostname or "")
    except (OSError, UnicodeError):
        return None


def crawl_starten(conn: sqlite3.Connection, projekt_id: int, warten: bool = False) -> dict:
    """Legt einen Crawl an und startet ihn im Hintergrund (oder blockierend mit warten=True).
    Pro Webserver (IP) läuft höchstens ein Crawl: parallele Crawls auf denselben Server vervielfachen die
    Last, und Hoster sperren dann die eigene IP (so passiert bei vier Domains auf einem Shared-Hosting)."""
    e = einstellungen_holen(conn, projekt_id)
    ziel_ip = server_ip(e["start_url"])
    for laufend_id, laufend_projekt, laufend_url in conn.execute(
            "SELECT id, projekt_id, start_url FROM crawls WHERE status='laeuft'").fetchall():
        if _ist_verwaist(conn, laufend_id):
            _abschliessen(conn, laufend_id, "abgebrochen", "Crawl-Prozess wurde beendet (kein Lebenszeichen)")
        elif laufend_projekt == projekt_id:
            raise AuditFehler(f"Crawl {laufend_id} läuft noch. Erst abwarten oder abbrechen.")
        elif ziel_ip and server_ip(laufend_url) == ziel_ip:
            raise AuditFehler(f"Crawl {laufend_id} läuft schon auf demselben Server ({ziel_ip}). Nacheinander "
                              "crawlen, sonst sperrt der Hoster womöglich deine IP.")
    cur = conn.execute(
        "INSERT INTO crawls (projekt_id, start_url, quelle, checks_aus, js_rendern, lebenszeichen)"
        " VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (projekt_id, e["start_url"], e["quelle"], e["checks_aus"], int(e["js_rendern"])))
    conn.commit()
    crawl_id = cur.lastrowid
    einst = CrawlEinstellungen(**{k: e[k] for k in CRAWLER_FELDER})

    args = (crawl_id, einst, e["ladezeit_auto"])
    if warten:
        _crawl_ausfuehren(*args)
    else:
        threading.Thread(target=_crawl_ausfuehren, args=args, daemon=True).start()
    return crawl_holen(conn, crawl_id)


def _crawl_ausfuehren(crawl_id: int, einst: CrawlEinstellungen, ladezeit: bool = False) -> None:
    """Läuft im eigenen Thread mit eigener DB-Verbindung. Hinterlässt den Crawl nie in 'laeuft'.
    ladezeit: danach im selben Thread die Ladezeit messen (nur bei vollständigem Crawl)."""
    try:
        with closing(verbinden()) as conn:
            try:
                Crawler(conn, crawl_id, einst).ausfuehren()
            except Exception as fehler:
                _abschliessen(conn, crawl_id, "fehler", f"{type(fehler).__name__}: {fehler}")
                return
            abgebrochen = conn.execute("SELECT abbrechen FROM crawls WHERE id=?", (crawl_id,)).fetchone()[0]
            _abschliessen(conn, crawl_id, "abgebrochen" if abgebrochen else "fertig")
            domain = conn.execute("SELECT p.domain FROM projekte p JOIN crawls c ON c.projekt_id = p.id"
                                  " WHERE c.id=?", (crawl_id,)).fetchone()[0]
            autoritaet.still_aktualisieren(conn, [domain])
            if ladezeit and not abgebrochen:
                _ladezeit_messen(conn, crawl_id)
    except Exception as fehler:  # letzte Rettung, z. B. DB beim Öffnen gesperrt
        with closing(verbinden()) as conn:
            conn.execute(
                "UPDATE crawls SET status='fehler', fehler_text=?, beendet_am=datetime('now')"
                " WHERE id=? AND status='laeuft'", (f"{type(fehler).__name__}: {fehler}"[:500], crawl_id))
            conn.commit()


def _ladezeit_messen(conn: sqlite3.Connection, crawl_id: int) -> None:
    """Automatische Messung nach dem Crawl. Fehler (z. B. schon eine Messung aktiv) lassen den Crawl unberührt."""
    from app.core import vitals   # zirkulären Import vermeiden
    try:
        vitals.starten(conn, crawl_id, warten=True)
    except vitals.VitalsFehler:
        pass


def _abschliessen(conn: sqlite3.Connection, crawl_id: int, status: str, fehler_text: str | None = None) -> None:
    """Checks auf die (ggf. unvollständigen) Daten anwenden, Health berechnen, Status setzen."""
    if conn.in_transaction:
        conn.rollback()
    if conn.execute("SELECT status FROM crawls WHERE id=?", (crawl_id,)).fetchone()[0] != "laeuft":
        return  # schon abgeschlossen (z. B. als verwaist), nicht überschreiben
    health = None
    try:
        linkrank.berechnen(conn, crawl_id)
        checks.ausfuehren(conn, crawl_id, _ausgeschlossen(conn, crawl_id))
        health = _health(conn, crawl_id)
    except Exception as fehler:
        conn.rollback()
        status, fehler_text = "fehler", f"Auswertung: {type(fehler).__name__}: {fehler}"
    conn.execute(
        "UPDATE crawls SET status=?, health=?, fehler_text=?, beendet_am=datetime('now') WHERE id=?",
        (status, health, fehler_text[:500] if fehler_text else None, crawl_id))
    conn.commit()


def crawl_abbrechen(conn: sqlite3.Connection, crawl_id: int) -> dict:
    """Laufender Crawl (egal in welchem Prozess) sieht das Flag und hört nach der aktuellen Seite auf.
    Ist der Crawl verwaist, wird er direkt mit den bisherigen Daten abgeschlossen."""
    c = crawl_holen(conn, crawl_id)
    if c["status"] != "laeuft":
        raise AuditFehler(f"Crawl {crawl_id} läuft nicht (Status: {c['status']})")
    conn.execute("UPDATE crawls SET abbrechen=1 WHERE id=?", (crawl_id,))
    conn.commit()
    if _ist_verwaist(conn, crawl_id):
        _abschliessen(conn, crawl_id, "abgebrochen", "Crawl-Prozess wurde beendet (kein Lebenszeichen)")
    return crawl_holen(conn, crawl_id)


def crawl_holen(conn: sqlite3.Connection, crawl_id: int) -> dict:
    z = conn.execute(
        "SELECT id, projekt_id, status, gestartet_am, beendet_am, start_url, seiten_anzahl, health, fehler_text,"
        " js_rendern FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    if z is None:
        raise AuditFehler(f"Crawl {crawl_id} nicht gefunden")
    return dict(z)


def crawls_liste(conn: sqlite3.Connection, projekt_id: int) -> list[dict]:
    projekte.holen(conn, projekt_id)
    ids = conn.execute("SELECT id FROM crawls WHERE projekt_id=? ORDER BY id DESC", (projekt_id,)).fetchall()
    return [crawl_holen(conn, z[0]) for z in ids]


def letzter_crawl_id(conn: sqlite3.Connection, projekt_id: int, nur_fertige: bool = True) -> int | None:
    bedingung = "AND status IN ('fertig', 'abgebrochen')" if nur_fertige else ""
    z = conn.execute(
        f"SELECT id FROM crawls WHERE projekt_id=? {bedingung} ORDER BY id DESC LIMIT 1", (projekt_id,)).fetchone()
    return z[0] if z else None


# ---------- Auswertung ----------

def _geprueft(conn: sqlite3.Connection, crawl_id: int) -> int:
    """Bezugsgröße für den Anteil betroffener Seiten: HTML-Seiten (ohne Bilder, PDFs, Weiterleitungen)."""
    html = conn.execute(f"SELECT COUNT(*) FROM seiten WHERE crawl_id=? AND {checks.katalog.HTML}", (crawl_id,)).fetchone()[0]
    return html or conn.execute("SELECT COUNT(*) FROM seiten WHERE crawl_id=?", (crawl_id,)).fetchone()[0]


def _treffer_pro_check(conn: sqlite3.Connection, crawl_id: int) -> dict[str, tuple[int, int, bool]]:
    """check_id → (issues, betroffene Seiten, betrifft ganze Site). Ausgeblendetes („Bewusst so“) zählt nicht."""
    return {
        z[0]: (z[1], z[2], bool(z[3]))
        for z in conn.execute(f"""
            SELECT i.check_id, COUNT(*), COUNT(DISTINCT i.seite_id), MAX(i.seite_id IS NULL)
            FROM issues i LEFT JOIN seiten s ON s.id = i.seite_id
            WHERE i.crawl_id=? AND {ausblenden.NICHT_AUSGEBLENDET} GROUP BY i.check_id""", (crawl_id,))
    }


def _ausgeschlossen(conn: sqlite3.Connection, crawl_id: int) -> set[str]:
    z = conn.execute("SELECT checks_aus FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    return set(liste(z[0])) if z else set()


def _bezug(conn: sqlite3.Connection, crawl_id: int) -> dict[str, int]:
    """Checks mit eigener Bezugsgröße: Ladezeit zählt gegen die gemessene Stichprobe, nicht gegen alle Seiten."""
    n = checks.ladezeit.gemessen(conn, crawl_id)
    return dict.fromkeys(checks.ladezeit.STICHPROBE, n) if n else {}


def neu_auswerten(conn: sqlite3.Connection, crawl_id: int) -> None:
    """Checks erneut anwenden und Zustand neu speichern, z. B. wenn nach dem Crawl die Ladezeit gemessen wurde."""
    checks.ausfuehren(conn, crawl_id, _ausgeschlossen(conn, crawl_id))
    conn.execute("UPDATE crawls SET health=? WHERE id=?", (_health(conn, crawl_id), crawl_id))
    conn.commit()


def _health(conn: sqlite3.Connection, crawl_id: int, kategorie: str | set[str] | None = None) -> float | None:
    """Health des ganzen Crawls oder nur eines Bereichs (bzw. mehrerer Bereiche).

    Im Bereich KI-Suche zählt Feinschliff mit Gewicht 1: Die KI-Checks sind fast alle Feinschliff, sonst stünde
    dort trotz vieler Funde 100. Für den Gesamt-Zustand bleibt Feinschliff bei 0."""
    if isinstance(kategorie, str):
        kategorie = {kategorie}
    feinschliff = kategorie == {"ki"}
    treffer = _treffer_pro_check(conn, crawl_id)
    aus = _ausgeschlossen(conn, crawl_id)
    bezug = _bezug(conn, crawl_id)
    eingaben = [
        ("warning" if feinschliff and c.schwere == "notice" else c.schwere,
         treffer.get(c.id, (0, 0, False))[1], treffer.get(c.id, (0, 0, False))[2], c.id, bezug.get(c.id))
        for c in checks.REGISTER.values()
        if (kategorie is None or c.kategorie in kategorie) and c.id not in aus
    ]
    return score.berechnen(eingaben, _geprueft(conn, crawl_id))


def uebersicht(conn: sqlite3.Connection, crawl_id: int) -> dict:
    """Daten für die Overview-Seite: Scores, Zähler, Seiten-Aufteilung, Top-Issues."""
    crawl = crawl_holen(conn, crawl_id)
    issues = issues_liste(conn, crawl_id)
    zaehler = {s: {"checks": 0, "issues": 0} for s in checks.SCHWEREGRADE}
    for i in issues:
        zaehler[i["schwere"]]["checks"] += 1
        zaehler[i["schwere"]]["issues"] += i["anzahl"]

    aufteilung = dict(conn.execute("""
        SELECT CASE
            WHEN s.blockiert = 1 THEN 'blockiert'
            WHEN s.status_code IS NULL OR s.status_code >= 400 THEN 'defekt'
            WHEN s.status_code BETWEEN 300 AND 399 THEN 'weiterleitung'
            ELSE 'ok' END AS art, COUNT(*)
        FROM seiten s WHERE s.crawl_id=? GROUP BY art""", (crawl_id,)).fetchall())
    # "Mit Problemen" = mindestens ein Error oder Warning; Notices allein gelten als gesund
    relevante = [c.id for c in checks.REGISTER.values() if c.schwere != "notice"]
    mit_problemen = conn.execute(f"""
        SELECT COUNT(DISTINCT i.seite_id) FROM issues i JOIN seiten s ON s.id = i.seite_id
        WHERE i.crawl_id=? AND s.status_code = 200 AND s.blockiert = 0 AND {ausblenden.NICHT_AUSGEBLENDET}
          AND i.check_id IN ({','.join('?' * len(relevante))})""", (crawl_id, *relevante)).fetchone()[0]
    ok = aufteilung.get("ok", 0)
    seiten = {
        "gesamt": crawl["seiten_anzahl"],
        "gesund": max(ok - mit_problemen, 0),
        "mit_problemen": mit_problemen,
        "defekt": aufteilung.get("defekt", 0),
        "weiterleitung": aufteilung.get("weiterleitung", 0),
        "blockiert": aufteilung.get("blockiert", 0),
    }

    rang = {s: n for n, s in enumerate(checks.SCHWEREGRADE)}
    top = sorted((i for i in issues if i["schwere"] != "notice"),
                 key=lambda i: (rang[i["schwere"]], -i["seiten"]))[:10]
    return {
        "crawl": crawl,
        "health": crawl["health"] if crawl["health"] is not None else _health(conn, crawl_id),
        "kategorien": [
            {"id": k, "name": name, "health": _health(conn, crawl_id, k),
             "issues": sum(i["anzahl"] for i in issues if i["kategorie"] == k),
             # Probleme = Prüfungen mit Treffern, die zählen; Feinschliff (notice) getrennt, Gewicht 0
             "probleme": sum(1 for i in issues if i["kategorie"] == k and i["schwere"] != "notice"),
             "feinschliff": sum(1 for i in issues if i["kategorie"] == k and i["schwere"] == "notice")}
            for k, name in checks.KATEGORIEN.items()
        ],
        "zaehler": zaehler,
        "seiten": seiten,
        "top_issues": top,
        # Website sieht nach JavaScript-App aus, wurde aber ohne JavaScript geprüft → Hinweis auf der Übersicht
        "js_hinweis": next((i["seiten"] for i in issues if i["id"] == "js_app_ohne_rendern"), 0),
    }


def issues_liste(conn: sqlite3.Connection, crawl_id: int, schwere: str | None = None,
                 kategorie: str | None = None) -> list[dict]:
    """Alle Checks mit Treffern, sortiert nach Schweregrad und Anzahl."""
    crawl_holen(conn, crawl_id)
    treffer = _treffer_pro_check(conn, crawl_id)
    rang = {s: n for n, s in enumerate(checks.SCHWEREGRADE)}
    ergebnis = []
    for check_id, (anzahl, seiten, ganze_site) in treffer.items():
        c = checks.REGISTER.get(check_id)
        if c is None or (schwere and c.schwere != schwere) or (kategorie and c.kategorie != kategorie):
            continue
        ergebnis.append({**c.als_dict(), "anzahl": anzahl, "seiten": seiten, "ganze_site": ganze_site})
    return sorted(ergebnis, key=lambda i: (rang[i["schwere"]], -i["anzahl"]))


def issue_details(conn: sqlite3.Connection, crawl_id: int, check_id: str, limit: int = 200) -> dict:
    c = checks.REGISTER.get(check_id)
    if c is None:
        raise AuditFehler(f"Unbekannter Check: {check_id}")
    zeilen = conn.execute("""
        SELECT s.url, i.detail FROM issues i LEFT JOIN seiten s ON s.id = i.seite_id
        WHERE i.crawl_id=? AND i.check_id=? ORDER BY s.url LIMIT ?""", (crawl_id, check_id, limit)).fetchall()
    regeln = ausblenden.regeln(conn, crawl_id)
    return {**c.als_dict(), "ausgeblendet": ausblenden.genau(regeln, check_id, None),
            "treffer": [{"url": z[0], "detail": z[1], "ausgeblendet": ausblenden.trifft(regeln, check_id, z[0])}
                        for z in zeilen]}


def seiten_liste(conn: sqlite3.Connection, crawl_id: int, suche: str | None = None,
                 nur_mit_problemen: bool = False, limit: int = 100, offset: int = 0) -> list[dict]:
    crawl_holen(conn, crawl_id)
    bedingungen, params = ["s.crawl_id = ?"], [crawl_id]
    if suche:
        bedingungen.append("s.url LIKE ?")
        params.append(f"%{suche}%")
    having = "HAVING COUNT(i.id) > 0" if nur_mit_problemen else ""
    zeilen = conn.execute(f"""
        SELECT s.id, s.url, s.status_code, s.tiefe, s.title, s.ladezeit_ms, s.woerter, s.blockiert, s.link_rank,
               COUNT(i.id) AS issues
        FROM seiten s LEFT JOIN issues i ON i.seite_id = s.id AND {ausblenden.NICHT_AUSGEBLENDET}
        WHERE {' AND '.join(bedingungen)}
        GROUP BY s.id {having} ORDER BY s.tiefe, s.url LIMIT ? OFFSET ?""",
        (*params, limit, offset)).fetchall()
    return [dict(z) for z in zeilen]


def seite_details(conn: sqlite3.Connection, crawl_id: int, url: str) -> dict:
    z = conn.execute("SELECT * FROM seiten WHERE crawl_id=? AND url=?", (crawl_id, url)).fetchone()
    if z is None:
        raise AuditFehler(f"Seite nicht im Crawl {crawl_id}: {url}")
    seite = dict(z)
    regeln = ausblenden.regeln(conn, crawl_id)
    seite["ausgeblendet"] = ausblenden.genau(regeln, None, url)
    seite["issues"] = [
        {**checks.REGISTER[i[0]].als_dict(), "detail": i[1], "ausgeblendet": ausblenden.trifft(regeln, i[0], url)}
        for i in conn.execute("SELECT check_id, detail FROM issues WHERE seite_id=?", (seite["id"],))
        if i[0] in checks.REGISTER
    ]
    seite["eingehende_links"] = conn.execute(
        "SELECT COUNT(DISTINCT seite_id) FROM links WHERE crawl_id=? AND ziel_url=? AND art='a'",
        (crawl_id, url)).fetchone()[0]
    return seite


def checks_katalog() -> list[dict]:
    return [c.als_dict() for c in checks.REGISTER.values()]
