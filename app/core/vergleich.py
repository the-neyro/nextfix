"""Service: Verlauf der Crawls eines Projekts und Vergleich zweier Crawls."""

import sqlite3

from app import checks
from app.core import ausblenden, projekte
from app.core.audit import AuditFehler, crawl_holen

FERTIG = "status IN ('fertig', 'abgebrochen')"
# Treffer je Check ohne Ausgeblendetes („Bewusst so“)
TREFFER_JE_CHECK = f"""SELECT i.check_id, COUNT(*) FROM issues i LEFT JOIN seiten s ON s.id = i.seite_id
    WHERE i.crawl_id=? AND {ausblenden.NICHT_AUSGEBLENDET} GROUP BY i.check_id"""


def _anzahl_je_schwere(conn: sqlite3.Connection, crawl_id: int) -> dict[str, int]:
    zaehler = dict.fromkeys(checks.SCHWEREGRADE, 0)
    for check_id, anzahl in conn.execute(TREFFER_JE_CHECK, (crawl_id,)):
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


def _treffer(conn: sqlite3.Connection, crawl_id: int) -> dict[str, int]:
    return dict(conn.execute(TREFFER_JE_CHECK, (crawl_id,)))


def vergleich(conn: sqlite3.Connection, crawl_id: int, vorher_id: int | None = None) -> dict:
    """Was hat sich seit dem vorherigen (oder angegebenen) Crawl geändert? Nur Checks mit Änderung."""
    jetzt, vorher = _vorher(conn, crawl_id, vorher_id)
    a, b = _treffer(conn, vorher["id"]), _treffer(conn, crawl_id)
    rang = {s: n for n, s in enumerate(checks.SCHWEREGRADE)}
    aenderungen = []
    for check_id in a.keys() | b.keys():
        c = checks.REGISTER.get(check_id)
        alt, neu = a.get(check_id, 0), b.get(check_id, 0)
        if c is None or alt == neu:
            continue
        status = "neu" if alt == 0 else "behoben" if neu == 0 else "mehr" if neu > alt else "weniger"
        aenderungen.append({"id": check_id, "name": c.name, "schwere": c.schwere, "kategorie": c.kategorie,
                            "vorher": alt, "jetzt": neu, "differenz": neu - alt, "status": status})
    aenderungen.sort(key=lambda x: (rang[x["schwere"]], -abs(x["differenz"])))

    def kopf(c: dict) -> dict:
        return {"id": c["id"], "gestartet_am": c["gestartet_am"], "seiten": c["seiten_anzahl"], "health": c["health"]}

    return {"vorher": kopf(vorher), "jetzt": kopf(jetzt), "aenderungen": aenderungen}


def treffer_vergleich(conn: sqlite3.Connection, crawl_id: int, check_id: str, vorher_id: int | None = None) -> dict:
    """Für einen Check: welche URLs sind neu betroffen, welche nicht mehr (Website-weit = None)."""
    if check_id not in checks.REGISTER:
        raise AuditFehler(f"Unbekannter Check: {check_id}")
    jetzt, vorher = _vorher(conn, crawl_id, vorher_id)

    def urls(cid: int) -> set[str | None]:
        return {z[0] for z in conn.execute(
            "SELECT s.url FROM issues i LEFT JOIN seiten s ON s.id = i.seite_id WHERE i.crawl_id=? AND i.check_id=?"
            f" AND {ausblenden.NICHT_AUSGEBLENDET}", (cid, check_id))}

    alt, neu = urls(vorher["id"]), urls(jetzt["id"])
    sortiert = lambda m: sorted(m, key=lambda u: u or "")  # noqa: E731
    return {"check_id": check_id, "vorher_id": vorher["id"], "neu": sortiert(neu - alt), "behoben": sortiert(alt - neu)}
