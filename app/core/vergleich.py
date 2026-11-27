"""Service: Verlauf der Crawls eines Projekts und Vergleich zweier Crawls."""

import sqlite3
from collections import Counter, defaultdict

from app import checks
from app.core import ausblenden, projekte
from app.core.audit import AuditFehler, crawl_holen
from app.core.nachpruefung import Nachpruefung

FERTIG = "status IN ('fertig', 'abgebrochen')"
# Treffer je Check ohne Ausgeblendetes („Bewusst so“)
TREFFER_JE_CHECK = f"""SELECT i.check_id, COUNT(*) FROM issues i LEFT JOIN seiten s ON s.id = i.seite_id
    WHERE i.crawl_id=? AND {ausblenden.NICHT_AUSGEBLENDET} GROUP BY i.check_id"""


def _treffer(conn: sqlite3.Connection, crawl_id: int) -> dict[str, int]:
    return dict(conn.execute(TREFFER_JE_CHECK, (crawl_id,)))


def _anzahl_je_schwere(conn: sqlite3.Connection, crawl_id: int) -> dict[str, int]:
    zaehler = dict.fromkeys(checks.SCHWEREGRADE, 0)
    for check_id, anzahl in _treffer(conn, crawl_id).items():
        if check_id in checks.REGISTER:
            zaehler[checks.REGISTER[check_id].schwere] += anzahl
    return zaehler


def verlauf(conn: sqlite3.Connection, projekt_id: int) -> list[dict]:
    """Abgeschlossene Crawls, älteste zuerst: Datum, Seiten, Health, Issues je Schweregrad."""
    projekte.holen(conn, projekt_id)
    zeilen = conn.execute(
        f"SELECT id, gestartet_am, seiten_anzahl, health FROM crawls WHERE projekt_id=? AND {FERTIG} ORDER BY id",
        (projekt_id,)).fetchall()
    return [{**dict(z), **_anzahl_je_schwere(conn, z["id"])} for z in zeilen]


def vorheriger_crawl_id(conn: sqlite3.Connection, crawl_id: int) -> int | None:
    crawl = crawl_holen(conn, crawl_id)
    z = conn.execute(f"SELECT MAX(id) FROM crawls WHERE projekt_id=? AND id < ? AND {FERTIG}",
                     (crawl["projekt_id"], crawl_id)).fetchone()
    return z[0]


def _vorher(conn: sqlite3.Connection, crawl_id: int, vorher_id: int | None) -> tuple[dict, dict]:
    jetzt = crawl_holen(conn, crawl_id)
    vorher_id = vorher_id or vorheriger_crawl_id(conn, crawl_id)
    if vorher_id is None:
        raise AuditFehler(f"Kein früherer Crawl zum Vergleich mit Crawl {crawl_id}")
    vorher = crawl_holen(conn, vorher_id)
    if vorher["projekt_id"] != jetzt["projekt_id"]:
        raise AuditFehler("Crawls gehören zu verschiedenen Projekten")
    return jetzt, vorher


def _fundstellen(conn, crawl_id, check_id=None):
    sql = f"""SELECT i.check_id, s.url FROM issues i LEFT JOIN seiten s ON s.id=i.seite_id
        WHERE i.crawl_id=? AND {ausblenden.NICHT_AUSGEBLENDET}"""
    parameter = (crawl_id,)
    if check_id is not None:
        sql += " AND i.check_id=?"
        parameter += (check_id,)
    fundstellen = defaultdict(list)
    for cid, url in conn.execute(sql, parameter):
        fundstellen[cid].append(url)
    return fundstellen


def _unterschiede(conn, jetzt, vorher, check_id=None):
    a = _fundstellen(conn, vorher["id"], check_id)
    b = _fundstellen(conn, jetzt["id"], check_id)
    nachpruefung = Nachpruefung(conn, jetzt, vorher)
    for cid in sorted(a.keys() | b.keys()):
        alt, neu = set(a[cid]), set(b[cid])
        offen = alt - neu
        # Mehrere Treffer auf einer Seite oder für die ganze Site können auf weniger Befunde zurückgehen.
        # Auch dafür muss die Grundlage der Prüfung noch vorliegen.
        a_anzahl, b_anzahl = Counter(a[cid]), Counter(b[cid])
        offen |= (a_anzahl - b_anzahl).keys() & neu
        unbestaetigt = {url for url in offen if not nachpruefung.bestaetigt(cid, url)}
        yield cid, len(a[cid]), len(b[cid]), neu - alt, alt - neu - unbestaetigt, unbestaetigt


def offene_nachpruefungen(conn: sqlite3.Connection, crawl_id: int) -> dict[str, set[str | None]]:
    """Offene Aufgaben über mehrere Crawls erhalten, bis Messdaten oder „Bewusst so“ sie klären."""
    jetzt = crawl_holen(conn, crawl_id)
    vorher_id = vorheriger_crawl_id(conn, crawl_id)
    if vorher_id is None:
        return {}
    # Der direkte Vergleich berücksichtigt auch weniger Treffer auf derselben Seite.
    offen = defaultdict(set)
    for cid, _, _, _, _, unbestaetigt in _unterschiede(conn, jetzt, crawl_holen(conn, vorher_id)):
        if unbestaetigt:
            offen[cid].update(unbestaetigt)

    aktuell = {cid: set(urls) for cid, urls in _fundstellen(conn, crawl_id).items()}
    gruppen = defaultdict(set)
    for cid, url, ursprung_id in conn.execute(f"""
            SELECT i.check_id, s.url, MAX(i.crawl_id)
            FROM issues i JOIN crawls c ON c.id=i.crawl_id LEFT JOIN seiten s ON s.id=i.seite_id
            WHERE c.projekt_id=? AND c.id<? AND c.status IN ('fertig', 'abgebrochen')
              AND {ausblenden.NICHT_AUSGEBLENDET}
            GROUP BY i.check_id, s.url
            """, (jetzt["projekt_id"], crawl_id)):
        check = checks.REGISTER.get(cid)
        if (check is not None and check.schwere != "notice" and ursprung_id != vorher_id
                and url not in aktuell.get(cid, ())):
            gruppen[ursprung_id].add((cid, url))
    if not gruppen:
        return dict(offen)

    crawls = {z["id"]: dict(z) for z in conn.execute("""
        SELECT id, status, start_url, js_rendern FROM crawls
        WHERE projekt_id=? AND id>=? AND id<? AND status IN ('fertig', 'abgebrochen') ORDER BY id DESC
        """, (jetzt["projekt_id"], min(gruppen), crawl_id))}
    for ursprung_id, fundstellen in gruppen.items():
        # Eine schon früher bestätigte Reparatur darf bei späteren Lücken nicht wieder offen werden.
        for messung in [jetzt, *crawls.values()]:
            if messung["id"] <= ursprung_id or messung["status"] != "fertig":
                continue
            nachpruefung = Nachpruefung(conn, messung, crawls[ursprung_id])
            fundstellen = {(cid, url) for cid, url in fundstellen if not nachpruefung.bestaetigt(cid, url)}
            if not fundstellen:
                break
        for cid, url in fundstellen:
            offen[cid].add(url)
    return dict(offen)


def vergleich(conn: sqlite3.Connection, crawl_id: int, vorher_id: int | None = None) -> dict:
    """Was hat sich seit dem vorherigen (oder angegebenen) Crawl geändert? Nur Checks mit Änderung."""
    jetzt, vorher = _vorher(conn, crawl_id, vorher_id)
    rang = {s: n for n, s in enumerate(checks.SCHWEREGRADE)}
    aenderungen = []
    for check_id, alt, neu, hinzu, behoben, unbestaetigt in _unterschiede(conn, jetzt, vorher):
        c = checks.REGISTER.get(check_id)
        if c is None or (alt == neu and not (hinzu or behoben or unbestaetigt)):
            continue
        if unbestaetigt:
            status = "nicht_nachgeprueft"
        elif alt == 0:
            status = "neu"
        elif neu == 0:
            status = "behoben"
        elif neu == alt:
            status = "geaendert"
        else:
            status = "mehr" if neu > alt else "weniger"
        aenderungen.append({"id": check_id, "name": c.name, "schwere": c.schwere, "kategorie": c.kategorie,
                            "vorher": alt, "jetzt": neu, "differenz": neu - alt, "status": status,
                            "nicht_nachgeprueft": len(unbestaetigt)})
    aenderungen.sort(key=lambda x: (rang[x["schwere"]], -abs(x["differenz"])))

    def kopf(c: dict) -> dict:
        return {"id": c["id"], "gestartet_am": c["gestartet_am"], "seiten": c["seiten_anzahl"],
                "health": c["health"], "status": c["status"]}

    return {"vorher": kopf(vorher), "jetzt": kopf(jetzt), "aenderungen": aenderungen}


def treffer_vergleich(conn: sqlite3.Connection, crawl_id: int, check_id: str, vorher_id: int | None = None) -> dict:
    """Neu betroffene, bestätigt behobene und nicht nachgeprüfte Fundstellen (Website-weit = None)."""
    if check_id not in checks.REGISTER:
        raise AuditFehler(f"Unbekannter Check: {check_id}")
    jetzt, vorher = _vorher(conn, crawl_id, vorher_id)
    diff = next(_unterschiede(conn, jetzt, vorher, check_id), None)
    neu, behoben, unbestaetigt = diff[3:] if diff else ((), (), ())
    return {"check_id": check_id, "vorher_id": vorher["id"],
            "neu": sorted(neu, key=lambda u: u or ""), "behoben": sorted(behoben, key=lambda u: u or ""),
            "nicht_nachgeprueft": sorted(unbestaetigt, key=lambda u: u or "")}
