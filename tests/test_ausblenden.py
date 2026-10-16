"""„Bewusst so“: ausgeblendete Probleme und Seiten zählen nicht mehr, Rücknahme stellt alles wieder her."""

import pytest

from app.core import audit, aufgaben, ausblenden, projekte


@pytest.fixture
def crawl(testseite):
    conn = audit.verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0)
    c = audit.crawl_starten(conn, p.id, warten=True)
    return conn, p.id, c["id"]


def _aufgaben_ids(conn, crawl_id) -> set[str]:
    return {a["id"] for a in aufgaben.liste(conn, crawl_id)["aufgaben"]}


def test_problem_ausblenden_und_zuruecknehmen(crawl):
    conn, projekt_id, crawl_id = crawl
    vorher = audit.crawl_holen(conn, crawl_id)["health"]
    assert "status_5xx" in _aufgaben_ids(conn, crawl_id)

    a = ausblenden.ausblenden(conn, projekt_id, check_id="status_5xx", grund="Testseite")
    assert a["art"] == "problem"
    assert "status_5xx" not in _aufgaben_ids(conn, crawl_id)
    assert "status_5xx" not in {i["id"] for i in audit.issues_liste(conn, crawl_id)}
    assert audit.crawl_holen(conn, crawl_id)["health"] > vorher   # gespeicherter Zustand neu berechnet
    assert audit.issue_details(conn, crawl_id, "status_5xx")["ausgeblendet"]   # Details bleiben erreichbar

    ausblenden.einblenden(conn, projekt_id, a["id"])
    assert audit.crawl_holen(conn, crawl_id)["health"] == vorher
    assert "status_5xx" in _aufgaben_ids(conn, crawl_id)


def test_seite_ausblenden(crawl, testseite):
    conn, projekt_id, crawl_id = crawl
    url = testseite + "schlecht"
    vorher = audit._treffer_pro_check(conn, crawl_id)["viewport_fehlt"][1]
    ausblenden.ausblenden(conn, projekt_id, url=url)
    assert "viewport_fehlt" not in audit._treffer_pro_check(conn, crawl_id)   # nur diese Seite hatte es
    assert vorher == 1
    s = audit.seite_details(conn, crawl_id, url)
    assert s["ausgeblendet"] and all(i["ausgeblendet"] for i in s["issues"])
    assert url not in {z["url"] for z in audit.seiten_liste(conn, crawl_id, nur_mit_problemen=True)}


def test_fundstelle_ausblenden_laesst_rest_stehen(crawl, testseite):
    conn, projekt_id, crawl_id = crawl
    ausblenden.ausblenden(conn, projekt_id, check_id="title_doppelt", url=testseite + "doppelt-1")
    assert audit._treffer_pro_check(conn, crawl_id)["title_doppelt"][1] == 1
    treffer = {t["url"]: bool(t["ausgeblendet"]) for t in audit.issue_details(conn, crawl_id, "title_doppelt")["treffer"]}
    assert treffer == {testseite + "doppelt-1": True, testseite + "doppelt-2": False}


def test_doppelt_ausblenden_legt_nichts_doppelt_an(crawl):
    conn, projekt_id, _ = crawl
    a = ausblenden.ausblenden(conn, projekt_id, check_id="status_5xx")
    b = ausblenden.ausblenden(conn, projekt_id, check_id="status_5xx", grund="neu")
    assert a["id"] == b["id"] and b["grund"] == "neu"
    assert len(ausblenden.liste(conn, projekt_id)) == 1


def test_ungueltige_eingaben(crawl):
    conn, projekt_id, _ = crawl
    with pytest.raises(ausblenden.AusblendenFehler):
        ausblenden.ausblenden(conn, projekt_id)
    with pytest.raises(ausblenden.AusblendenFehler):
        ausblenden.ausblenden(conn, projekt_id, check_id="gibt_es_nicht")
    with pytest.raises(ausblenden.AusblendenFehler):
        ausblenden.einblenden(conn, projekt_id, 999)
