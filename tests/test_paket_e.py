"""Paket E: Verlauf, Crawl-Vergleich (auf vorbereiteten DB-Zeilen)."""

import pytest

from app.core import projekte, vergleich
from app.core.audit import AuditFehler
from app.db import verbinden

B = "https://ex.de/"


def crawl_mit_issues(conn, projekt_id, issues: dict[str, list[str | None]], health=90.0) -> int:
    """Fertigen Crawl anlegen; issues: check_id → Pfade (None = ganze Website)."""
    c = conn.execute("INSERT INTO crawls (projekt_id, start_url, status, health) VALUES (?, ?, 'fertig', ?)",
                     (projekt_id, B, health)).lastrowid
    for check_id, pfade in issues.items():
        for pfad in pfade:
            seite_id = None
            if pfad is not None:
                seite_id = conn.execute("INSERT OR IGNORE INTO seiten (crawl_id, url, tiefe) VALUES (?, ?, 1)",
                                        (c, B + pfad)).lastrowid or conn.execute(
                    "SELECT id FROM seiten WHERE crawl_id=? AND url=?", (c, B + pfad)).fetchone()[0]
            conn.execute("INSERT INTO issues (crawl_id, check_id, seite_id) VALUES (?, ?, ?)", (c, check_id, seite_id))
    return c


@pytest.fixture
def zwei_crawls():
    conn = verbinden()
    p = projekte.anlegen(conn, "ex.de").id
    alt = crawl_mit_issues(conn, p, {"title_fehlt": ["a", "b"], "mixed_content": ["a"], "llms_fehlt": [None]}, 80.0)
    neu = crawl_mit_issues(conn, p, {"title_fehlt": ["b", "c", "d"], "llms_fehlt": [None], "kein_hsts": [None]}, 85.0)
    return conn, p, alt, neu


def test_verlauf(zwei_crawls):
    conn, p, alt, neu = zwei_crawls
    v = vergleich.verlauf(conn, p)
    assert [z["id"] for z in v] == [alt, neu]
    assert (v[0]["error"], v[0]["warning"], v[0]["notice"]) == (3, 0, 1)
    assert v[1]["health"] == 85.0


def test_vergleich(zwei_crawls):
    conn, p, alt, neu = zwei_crawls
    r = vergleich.vergleich(conn, neu)
    assert r["vorher"]["id"] == alt
    status = {a["id"]: (a["status"], a["differenz"]) for a in r["aenderungen"]}
    assert status == {"title_fehlt": ("mehr", 1), "mixed_content": ("behoben", -1), "kein_hsts": ("neu", 1)}


def test_treffer_vergleich(zwei_crawls):
    conn, p, alt, neu = zwei_crawls
    r = vergleich.treffer_vergleich(conn, neu, "title_fehlt")
    assert r["neu"] == [B + "c", B + "d"] and r["behoben"] == [B + "a"]
    assert vergleich.treffer_vergleich(conn, neu, "kein_hsts")["neu"] == [None]


def test_vergleich_ohne_vorgaenger(zwei_crawls):
    conn, p, alt, neu = zwei_crawls
    with pytest.raises(AuditFehler):
        vergleich.vergleich(conn, alt)
    anderes = projekte.anlegen(conn, "anders.de").id
    fremd = crawl_mit_issues(conn, anderes, {})
    with pytest.raises(AuditFehler):
        vergleich.vergleich(conn, neu, vorher_id=fremd)


# ---------- CSV-Export ----------

def test_csv_export(zwei_crawls):
    import csv
    from app.core import export
    conn, p, alt, neu = zwei_crawls
    text = export.issues_csv(conn, neu)
    assert text.startswith("﻿Schweregrad;")
    zeilen = list(csv.reader(text.lstrip("﻿").splitlines(), delimiter=";"))
    assert len(zeilen) == 1 + 5
    assert zeilen[1][0] == "error" and zeilen[-1][4] == "ganze Website"   # errors zuerst, Website-weit ohne URL
    seiten = list(csv.reader(export.seiten_csv(conn, neu).lstrip("﻿").splitlines(), delimiter=";"))
    assert seiten[0][0] == "url" and seiten[0][-1] == "issues" and len(seiten) == 1 + 3


def test_csv_api(zwei_crawls):
    from fastapi.testclient import TestClient
    from app.web import app
    conn, p, alt, neu = zwei_crawls
    conn.commit()
    r = TestClient(app).get(f"/api/crawls/{neu}/export/issues.csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert TestClient(app).get(f"/api/crawls/{neu}/export/quatsch.csv").status_code == 404


# ---------- URL-Filter ----------

def test_url_filter():
    from app.crawler.filter import UrlFilter, liste
    assert liste("/blog/\n , /shop/,") == ["/blog/", "/shop/"]
    f = UrlFilter(erlauben=["/blog/", "/$"], sperren=["/blog/entwurf", "sort="])
    assert f.erlaubt("https://ex.de/blog/artikel")
    assert f.erlaubt("https://ex.de/")
    assert not f.erlaubt("https://ex.de/shop/")
    assert not f.erlaubt("https://ex.de/blog/entwurf-1")
    assert not f.erlaubt("https://ex.de/blog/liste?seite=2&sort=neu")
    assert UrlFilter(sperren=["/shop/*/details"]).erlaubt("https://ex.de/shop/a/b") is True
    assert UrlFilter(sperren=["/shop/*/details"]).erlaubt("https://ex.de/shop/a/details") is False


def test_url_filter_parameter():
    from app.crawler.filter import UrlFilter
    f = UrlFilter(parameter=["utm_source", "SessionID"])
    assert f.bereinigen("https://ex.de/a?utm_source=x&seite=2&sessionid=9") == "https://ex.de/a?seite=2"
    assert f.bereinigen("https://ex.de/a?utm_source=x") == "https://ex.de/a"
    assert UrlFilter(parameter=["*"]).bereinigen("https://ex.de/a?x=1&y=2") == "https://ex.de/a"
    assert UrlFilter().bereinigen("https://ex.de/a?x=1") == "https://ex.de/a?x=1"


def test_crawl_mit_filtern_und_checks_aus(testseite):
    from app.core import audit
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0, sperren="/doppelt-",
                               parameter_entfernen=["variante"], checks_aus=["title_zu_kurz"])
    with pytest.raises(AuditFehler):
        audit.einstellungen_setzen(conn, p.id, checks_aus=["gibt_es_nicht"])
    c = audit.crawl_starten(conn, p.id, warten=True)
    urls = {z[0] for z in conn.execute("SELECT url FROM seiten WHERE crawl_id=?", (c["id"],))}
    assert testseite + "gut" in urls
    assert not {testseite + "doppelt-1", testseite + "doppelt-2", testseite + "gut?variante=2"} & urls
    assert "title_zu_kurz" not in {i["id"] for i in audit.issues_liste(conn, c["id"])}
    assert audit.crawl_holen(conn, c["id"])["health"] is not None


def test_einstellungen_web_formular():
    from fastapi.testclient import TestClient
    from app.core import audit
    from app.web import app
    conn = verbinden()
    p = projekte.anlegen(conn, "ex.de").id
    form = {"start_url": B, "seitenlimit": 50, "crawl_delay": 0.5, "user_agent": "x", "robots_beachten": 1,
            "quelle": "website", "sperren": "/a/\r\n/b/", "parameter_entfernen": "utm_source",
            "checks_aus": ["kein_hsts", "llms_fehlt"]}
    r = TestClient(app).post(f"/projekte/{p}/einstellungen", data=form)
    assert "Gespeichert" in r.text
    e = audit.einstellungen_holen(conn, p)
    assert (e["sperren"], e["checks_aus"]) == ("/a/\n/b/", "kein_hsts\nllms_fehlt")
    del form["checks_aus"]   # keine Checkbox angehakt = Liste leeren
    TestClient(app).post(f"/projekte/{p}/einstellungen", data=form)
    assert audit.einstellungen_holen(conn, p)["checks_aus"] == ""


# ---------- Interne Link-Stärke ----------

def test_pagerank_und_skala():
    from app.core.linkrank import pagerank, skalieren
    # 1 = Startseite, verlinkt 2 und 3; 2 und 3 verlinken zurück; 4 bekommt nur einen Link von 3
    rang = pagerank({1: {2, 3}, 2: {1}, 3: {1, 4}}, [1, 2, 3, 4])
    assert abs(sum(rang.values()) - 1) < 1e-9
    werte = skalieren(rang)
    assert werte[1] == 100 and werte[4] == 0
    assert werte[1] > werte[2] > werte[4]
    assert skalieren({1: 0.5, 2: 0.5}) == {1: 100, 2: 100}


def test_link_rank_im_crawl(testseite):
    from app.core import audit
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0)
    c = audit.crawl_starten(conn, p.id, warten=True)
    raenge = dict(conn.execute("SELECT url, link_rank FROM seiten WHERE crawl_id=? AND link_rank IS NOT NULL", (c["id"],)))
    assert raenge[testseite] == 100
    # alle Unterseiten hängen nur an der Startseite: gleich stark und schwächer als die Startseite
    assert raenge[testseite + "gut"] == raenge[testseite + "doppelt-1"] < 100
    assert testseite + "kaputt" not in raenge


# ---------- Thematische Berichte ----------

def test_themen_berichte(testseite):
    from fastapi.testclient import TestClient
    from app import checks
    from app.core import audit, themen
    from app.web import app
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0)
    c = audit.crawl_starten(conn, p.id, warten=True)["id"]
    for k in checks.KATEGORIEN:
        t = themen.thema(conn, c, k)
        assert t["kennzahlen"] and all(kz["titel"] for kz in t["kennzahlen"]), k
        assert all(i["kategorie"] == k for i in t["issues"])
        assert TestClient(app).get(f"/crawls/{c}/themen/{k}").status_code == 200
    status = {z["label"]: z["wert"] for z in themen.thema(conn, c, "crawlbarkeit")["kennzahlen"][1]["zeilen"]}
    assert status["4xx"] == 1 and status["5xx"] == 1 and status["blockiert (robots.txt)"] == 1
    with pytest.raises(AuditFehler):
        themen.thema(conn, c, "gibt_es_nicht")


# ---------- PDF-Bericht ----------

def test_pdf_bericht(testseite):
    from fastapi.testclient import TestClient
    from app import berichte
    from app.core import audit
    from app.web import app
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0)
    c = audit.crawl_starten(conn, p.id, warten=True)["id"]
    html = berichte.site_audit_html(conn, c)
    assert "Prüfbericht" in html and "Maßnahmen" in html and "Crawlbarkeit" in html and "KI-Suche" in html
    r = TestClient(app).get(f"/api/crawls/{c}/export/bericht.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and len(r.content) > 10_000
