"""Ende-zu-Ende: Crawl der lokalen Testseite, Checks, Score, Auswertung."""

import pytest

from app.core import audit, projekte, score
from app.crawler.parser import zerlegen
from app.crawler.urls import ist_intern, normalisieren
from app.db import verbinden


@pytest.fixture
def crawl(testseite):
    """Fertiger Crawl der Testseite → (conn, crawl_id)."""
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0)
    c = audit.crawl_starten(conn, p.id, warten=True)
    return conn, c["id"]


def _treffer(conn, crawl_id, check_id) -> set[str]:
    return {t["url"] or "SITE" for t in audit.issue_details(conn, crawl_id, check_id)["treffer"]}


def test_crawl_laeuft_durch(crawl, testseite):
    conn, crawl_id = crawl
    c = audit.crawl_holen(conn, crawl_id)
    assert c["status"] == "fertig", c["fehler_text"]
    assert c["seiten_anzahl"] == 11
    assert 0 <= c["health"] < 100


@pytest.mark.parametrize("check_id, pfade", [
    ("status_4xx", {"kaputt"}),
    ("status_5xx", {"serverfehler"}),
    ("title_fehlt", {"ohne-title"}),
    ("title_doppelt", {"doppelt-1", "doppelt-2"}),
    ("meta_desc_doppelt", {"doppelt-1", "doppelt-2"}),
    ("title_zu_kurz", {"schlecht"}),
    ("mehrere_h1", {"schlecht"}),
    ("wenig_text", {"schlecht"}),
    ("viewport_fehlt", {"schlecht"}),
    ("ohne_doctype", {"schlecht"}),
    ("ohne_lang", {"schlecht"}),
    ("ohne_charset", {"schlecht"}),
    ("meta_refresh", {"schlecht"}),
    ("bilder_ohne_alt", {"schlecht"}),
    ("interne_bilder_defekt", {"schlecht"}),
    ("interne_links_defekt", {"", "schlecht"}),
    ("temp_redirect", {"umleitung"}),
    ("blockiert", {"privat/geheim"}),
    ("interne_links_nofollow", {""}),
    ("externe_nofollow", {""}),
    ("links_ohne_anker", {""}),
    ("nichtssagender_anker", {"", "schlecht"}),
    ("js_css_unkomprimiert", {"schlecht"}),
    ("js_css_nicht_minifiziert", {"schlecht"}),
    ("externe_links_defekt", {""}),
])
def test_checks_finden_eingebaute_fehler(crawl, testseite, check_id, pfade):
    conn, crawl_id = crawl
    assert _treffer(conn, crawl_id, check_id) == {testseite + p for p in pfade}


def test_canonical_variante_kein_duplikat(crawl, testseite):
    """Regression (echte Website): ?paket=…-Varianten mit Canonical galten als doppelter Title."""
    conn, crawl_id = crawl
    assert testseite + "gut?variante=2" not in _treffer(conn, crawl_id, "title_doppelt")
    assert testseite + "gut?variante=2" not in _treffer(conn, crawl_id, "nur_ein_eingehender_link")


def test_site_weite_checks(crawl):
    conn, crawl_id = crawl
    assert _treffer(conn, crawl_id, "robots_formatfehler") == {"SITE"}
    assert _treffer(conn, crawl_id, "ki_bots_blockiert") == {"SITE"}
    assert _treffer(conn, crawl_id, "llms_format") == {"SITE"}
    assert _treffer(conn, crawl_id, "llms_fehlt") == set()
    assert _treffer(conn, crawl_id, "sitemap_fehlt") == set()
    assert _treffer(conn, crawl_id, "sitemap_nicht_in_robots") == set()
    assert _treffer(conn, crawl_id, "startseite_ohne_https") == {"SITE"}
    assert _treffer(conn, crawl_id, "robots_fehlt") == set()


def test_sitemap_checks(crawl, testseite):
    conn, crawl_id = crawl
    falsche = audit.issue_details(conn, crawl_id, "sitemap_falsche_seiten")["treffer"]
    details = {(t["url"] or "").replace(testseite, ""): t["detail"] for t in falsche}
    assert details["kaputt"] == "Status 404"
    assert details["umleitung"] == "Status 302"
    assert details["doppelt-1"] == "2× in Sitemap"
    assert "gut" not in details
    assert details["gut?variante=2"].startswith("Canonical auf")
    assert "verwaist" not in details
    orphans = audit.issue_details(conn, crawl_id, "orphan_sitemap")["treffer"]
    assert [t["detail"] for t in orphans] == [testseite + "verwaist – kein interner Link"]


def test_gute_seite_ohne_errors(crawl, testseite):
    conn, crawl_id = crawl
    s = audit.seite_details(conn, crawl_id, testseite + "gut")
    assert not [i for i in s["issues"] if i["schwere"] == "error"]
    assert s["eingehende_links"] == 1


def test_uebersicht(crawl):
    conn, crawl_id = crawl
    ue = audit.uebersicht(conn, crawl_id)
    assert ue["seiten"]["defekt"] == 2
    assert ue["seiten"]["weiterleitung"] == 1
    assert ue["seiten"]["blockiert"] == 1
    assert ue["zaehler"]["error"]["checks"] > 0
    assert ue["top_issues"][0]["schwere"] == "error"
    assert {k["id"] for k in ue["kategorien"]} >= {"crawlbarkeit", "inhalt", "links"}


def test_seitenlimit_und_einstellungen(testseite):
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    with pytest.raises(audit.AuditFehler):
        audit.einstellungen_setzen(conn, p.id, seitenlimit=0)
    with pytest.raises(audit.AuditFehler):
        audit.einstellungen_setzen(conn, p.id, start_url="ftp://x")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, seitenlimit=3, crawl_delay=0)
    c = audit.crawl_starten(conn, p.id, warten=True)
    assert c["seiten_anzahl"] == 3


def test_robots_ignorieren(testseite):
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0, robots_beachten=False)
    c = audit.crawl_starten(conn, p.id, warten=True)
    assert _treffer(conn, c["id"], "blockiert") == set()


def test_zweiter_crawl_waehrend_laufendem_abgelehnt():
    conn = verbinden()
    p = projekte.anlegen(conn, "example.de")
    conn.execute("INSERT INTO crawls (projekt_id, start_url, lebenszeichen) VALUES (?, 'x', datetime('now'))", (p.id,))
    conn.commit()
    crawl_id = audit.letzter_crawl_id(conn, p.id, nur_fertige=False)
    with pytest.raises(audit.AuditFehler, match="läuft noch"):
        audit.crawl_starten(conn, p.id)
    # Lebender Crawl: Abbrechen setzt nur das Flag, der Crawler beendet sich selbst
    assert audit.crawl_abbrechen(conn, crawl_id)["status"] == "laeuft"


def test_verwaister_crawl_wird_abgeschlossen(testseite):
    """Crawl-Prozess tot (kein Lebenszeichen) → blockiert keine neuen Crawls."""
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0)
    conn.execute("INSERT INTO crawls (projekt_id, start_url, lebenszeichen)"
                 " VALUES (?, 'x', datetime('now', '-10 minutes'))", (p.id,))
    conn.commit()
    alt = audit.letzter_crawl_id(conn, p.id, nur_fertige=False)
    neu = audit.crawl_starten(conn, p.id, warten=True)
    assert neu["status"] == "fertig"
    assert audit.crawl_holen(conn, alt)["status"] == "abgebrochen"


def test_keine_offene_transaktion_nach_blockierter_seite(testseite):
    """Regression: nach einer per robots.txt gesperrten Seite blieb die DB gesperrt."""
    import httpx
    from app.crawler.crawler import CrawlEinstellungen, Crawler

    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    crawl_id = conn.execute("INSERT INTO crawls (projekt_id, start_url) VALUES (?, ?)", (p.id, testseite)).lastrowid
    conn.commit()
    offen = []
    client = httpx.Client(event_hooks={"request": [lambda r: offen.append(conn.in_transaction)]})
    Crawler(conn, crawl_id, CrawlEinstellungen(start_url=testseite, crawl_delay=0), client).ausfuehren()
    assert offen and not any(offen)


def test_robots_hinter_weiterleitung():
    """Regression: robots.txt hinter 301 (z. B. auf www.) wurde ignoriert."""
    import httpx
    from app.crawler.crawler import CrawlEinstellungen, Crawler

    def antwort(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://a.de/robots.txt":
            return httpx.Response(301, headers={"Location": "https://www.a.de/robots.txt"})
        if url == "https://www.a.de/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /privat\nSitemap: https://www.a.de/sm.xml")
        if url == "https://www.a.de/sm.xml":
            return httpx.Response(200, text="<urlset/>")
        if url == "https://a.de/":
            return httpx.Response(200, headers={"Content-Type": "text/html"},
                                  text='<html><body><a href="/privat">p</a></body></html>')
        return httpx.Response(404)

    conn = verbinden()
    p = projekte.anlegen(conn, "a.de")
    crawl_id = conn.execute("INSERT INTO crawls (projekt_id, start_url) VALUES (?, 'https://a.de/')", (p.id,)).lastrowid
    conn.commit()
    client = httpx.Client(transport=httpx.MockTransport(antwort))
    Crawler(conn, crawl_id, CrawlEinstellungen(start_url="https://a.de/", crawl_delay=0), client).ausfuehren()
    c = conn.execute("SELECT robots_status, sitemap_status FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    assert tuple(c) == (200, 200)
    blockiert = conn.execute("SELECT blockiert FROM seiten WHERE url='https://a.de/privat'").fetchone()[0]
    assert blockiert == 1


# ---------- Einheiten ----------

def test_score_regeln():
    alles_gut = score.berechnen([("error", 0, False), ("warning", 0, False)], 10)
    assert alles_gut == 100
    # Einen Check komplett beheben bringt mehr als verstreut gleich viele Seiten
    ein_check = score.berechnen([("error", 2, False), ("error", 0, False)], 10)
    zwei_checks = score.berechnen([("error", 1, False), ("error", 1, False)], 10)
    assert ein_check > zwei_checks
    # Unabhängig von der Seitenzahl bei gleichem Anteil
    assert score.berechnen([("error", 1, False), ("error", 0, False)], 10) == \
           score.berechnen([("error", 10, False), ("error", 0, False)], 100)
    # Notices zählen nicht
    assert score.berechnen([("notice", 5, False), ("error", 0, False)], 10) == 100
    assert score.berechnen([("notice", 5, False)], 10) is None


def test_urls():
    assert normalisieren("../a#x", "https://ex.de/b/c") == "https://ex.de/a"
    assert normalisieren("mailto:a@b.de", "https://ex.de/") is None
    # Umlaute: kodiert und unkodiert sind dieselbe URL (sonst Fehlalarm „Canonical auf andere URL“)
    assert normalisieren("/sven-thöne/", "https://ex.de/") == normalisieren("/sven-th%C3%B6ne/", "https://ex.de/") \
        == "https://ex.de/sven-th%C3%B6ne/"
    assert normalisieren("/s?q=a b&x=ü", "https://ex.de/") == "https://ex.de/s?q=a%20b&x=%C3%BC"
    assert normalisieren("HTTPS://EX.DE", "https://ex.de/") == "https://ex.de/"
    assert ist_intern("https://www.ex.de/x", "ex.de")
    assert not ist_intern("https://shop.ex.de/x", "ex.de")


def test_parser_bild_link_und_base():
    i = zerlegen('<html><head><base href="/sub/"></head><body><a href="x"><img src="y.png" alt="Logo"></a></body></html>',
                 "https://ex.de/start")
    assert [(l.url, l.anker_text) for l in i.links if l.art == "a"] == [("https://ex.de/sub/x", "Logo")]


def test_parser_aria_label_als_linktext():
    """Regression (echte Website): Social-Icons mit aria-label galten als Links ohne Anchor-Text."""
    i = zerlegen('<a href="/x" aria-label="Radhaus bei LinkedIn"><svg></svg></a><a href="/y" title="Titel"></a><a href="/z"></a>',
                 "https://ex.de/")
    assert [l.anker_text for l in i.links] == ["Radhaus bei LinkedIn", "Titel", None]


def test_kein_paralleler_crawl_auf_denselben_server(testseite):
    """Zwei Projekte, ein Server (127.0.0.1 / localhost): zweiter Crawl wird abgelehnt, solange der erste läuft."""
    conn = verbinden()
    a = projekte.anlegen(conn, "127.0.0.1").id
    b = projekte.anlegen(conn, "localhost.test").id
    audit.einstellungen_setzen(conn, b, start_url=testseite.replace("127.0.0.1", "localhost"))
    conn.execute("INSERT INTO crawls (projekt_id, start_url, status, lebenszeichen) VALUES (?, ?, 'laeuft', datetime('now'))",
                 (a, testseite))
    conn.commit()
    with pytest.raises(audit.AuditFehler, match="demselben Server"):
        audit.crawl_starten(conn, b)


def test_score_schwache_website_nicht_schoengerechnet():
    """Fassung 2: Probleme verdünnen sich nicht über ~100 nie anschlagende Checks (eine schwache Website bekam vorher 95)."""
    nie = [("error", 0, False)] * 60 + [("warning", 0, False)] * 30
    duenn = nie + [("warning", 116, False, "wenig_text"), ("warning", 22, False), ("error", 8, False),
                   ("error", 2, False), ("warning", 2, False), ("error", 1, False)]
    # Fassung 3: „Wenig Text“ wiegt wie eine Warnung (Google wertet Länge allein nicht) → ~72 statt ~61, aber nicht 95
    assert 65 <= score.berechnen(duenn, 182) <= 80
    assert score.berechnen([("warning", 100, False, "wenig_text")], 182) == score.berechnen([("warning", 100, False)], 182)
    # Saubere Website mit Kleinigkeiten bleibt im grünen Bereich
    assert score.berechnen(nie + [("warning", 20, False), ("warning", 9, False)], 144) >= 90


def test_wirkung_als_stufe_statt_punkte(crawl):
    from app.core import aufgaben
    # Stufen nach Abzug: Fehler mindestens „mittel“, Warnung erst auf vielen Seiten
    assert aufgaben.wirkung(score.strafe("error", 1, False, 200)) == "mittel"
    assert aufgaben.wirkung(score.strafe("error", 50, False, 200)) == "hoch"
    assert aufgaben.wirkung(score.strafe("warning", 1, False, 200)) == "gering"
    assert aufgaben.wirkung(score.strafe("warning", 80, False, 200)) == "mittel"
    assert aufgaben.wirkung(score.strafe("warning", 0, True, 200)) == "hoch"
    conn, crawl_id = crawl
    liste = aufgaben.liste(conn, crawl_id)["aufgaben"]
    assert all(a["wirkung"] in ("hoch", "mittel", "gering") for a in liste)
    rang = {"hoch": 0, "mittel": 1, "gering": 2}
    assert [rang[a["wirkung"]] for a in liste] == sorted(rang[a["wirkung"]] for a in liste)   # passt zur Reihenfolge
