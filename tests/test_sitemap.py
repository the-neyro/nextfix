"""Sitemap-Lader: Index, gzip, Formatfehler; Crawl-Quelle 'sitemap'."""

import gzip

import httpx

from app.core import audit, projekte
from app.crawler import sitemap
from app.db import verbinden

URLSET = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{}</urlset>'


def _client(routen: dict) -> httpx.Client:
    def antwort(request):
        inhalt = routen.get(str(request.url))
        return httpx.Response(200, content=inhalt) if inhalt is not None else httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(antwort))


def test_index_mit_gzip_und_fehlern():
    routen = {
        "https://ex.de/index.xml": b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                   b"<sitemap><loc>https://ex.de/a.xml.gz</loc></sitemap>"
                                   b"<sitemap><loc>https://ex.de/kaputt.xml</loc></sitemap>"
                                   b"<sitemap><loc>https://ex.de/fehlt.xml</loc></sitemap></sitemapindex>",
        "https://ex.de/a.xml.gz": gzip.compress(URLSET.format(
            "<url><loc>https://ex.de/x</loc></url><url><loc> https://ex.de/y#z </loc></url>").encode()),
        "https://ex.de/kaputt.xml": b"<urlset><url><loc>https://ex.de/q</loc></url>",
    }
    e = sitemap.laden(_client(routen), ["https://ex.de/index.xml"])
    dateien = {d.url: d for d in e.dateien}
    assert dateien["https://ex.de/index.xml"].ist_index and dateien["https://ex.de/index.xml"].url_anzahl == 3
    assert dateien["https://ex.de/a.xml.gz"].url_anzahl == 2
    assert dateien["https://ex.de/kaputt.xml"].fehler.startswith("XML")
    assert dateien["https://ex.de/fehlt.xml"].status == 404
    assert [u for u, _ in e.eintraege] == ["https://ex.de/x", "https://ex.de/y"]


def test_falsches_wurzelelement():
    e = sitemap.laden(_client({"https://ex.de/s.xml": b"<html><loc>x</loc></html>"}), ["https://ex.de/s.xml"])
    assert "Wurzelelement" in e.dateien[0].fehler


def test_crawl_quelle_sitemap(testseite):
    """Nur Sitemap-URLs crawlen, keinen Links folgen."""
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0, quelle="sitemap")
    c = audit.crawl_starten(conn, p.id, warten=True)
    urls = {s["url"].replace(testseite, "") for s in audit.seiten_liste(conn, c["id"])}
    assert urls == {"gut", "doppelt-1", "kaputt", "umleitung", "gut?variante=2", "verwaist"}
    assert audit.issue_details(conn, c["id"], "orphan_sitemap")["treffer"] == []


def test_crawl_quelle_beides(testseite):
    """Links folgen, danach verwaiste Sitemap-URLs mitnehmen – und sie trotzdem als verwaist melden."""
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0, quelle="website")
    nur_links = {s["url"] for s in audit.seiten_liste(conn, audit.crawl_starten(conn, p.id, warten=True)["id"], limit=1000)}
    audit.einstellungen_setzen(conn, p.id, quelle="beides")
    c = audit.crawl_starten(conn, p.id, warten=True)
    beides = {s["url"] for s in audit.seiten_liste(conn, c["id"], limit=1000)}
    assert testseite + "verwaist" in beides and testseite + "verwaist" not in nur_links
    assert nur_links <= beides
    treffer = audit.issue_details(conn, c["id"], "orphan_sitemap")["treffer"]
    assert any("verwaist" in (t.get("url") or "") + (t.get("detail") or "") for t in treffer)
    with __import__("pytest").raises(audit.AuditFehler):
        audit.einstellungen_setzen(conn, p.id, quelle="alles")
