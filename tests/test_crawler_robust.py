"""Crawler-Robustheit: Umlaut-Domains, Zeichensätze, robots.txt wie Google, große Dateien."""

import httpx

from app.core import projekte
from app.crawler import crawler as crawler_modul
from app.crawler.crawler import CrawlEinstellungen, Crawler
from app.crawler.parser import dekodieren
from app.crawler.robots import RobotsTxt
from app.crawler.urls import host, ist_intern, normalisieren
from app.db import verbinden

PUNY = "xn--bckerei-mller-bfb28a.de"   # bäckerei-müller.de


def _crawlen(start_url, antwort, **einst):
    conn = verbinden()
    p = projekte.anlegen(conn, host(start_url))
    crawl_id = conn.execute("INSERT INTO crawls (projekt_id, start_url) VALUES (?, ?)", (p.id, start_url)).lastrowid
    conn.commit()
    client = httpx.Client(transport=httpx.MockTransport(antwort))
    Crawler(conn, crawl_id, CrawlEinstellungen(start_url=start_url, crawl_delay=0, **einst), client).ausfuehren()
    return {z[0]: z[1:] for z in conn.execute(
        "SELECT url, status_code, title, html_bytes FROM seiten WHERE crawl_id=?", (crawl_id,))}


def _html(text, **kw):
    return httpx.Response(200, headers={"Content-Type": "text/html; charset=utf-8"}, text=text, **kw)


# ---------- 1. Umlaut-Domains und Standard-Port ----------

def test_umlaut_domain_und_punycode_sind_dieselbe_website():
    assert host("https://bäckerei-müller.de/") == PUNY
    assert ist_intern(f"https://{PUNY}/kontakt", "bäckerei-müller.de")
    assert ist_intern("https://bäckerei-müller.de/kontakt", PUNY)
    assert normalisieren("https://x.de:443/a", "https://x.de/") == "https://x.de/a"
    assert normalisieren("http://x.de:8080/a", "http://x.de/") == "http://x.de:8080/a"


def test_crawl_folgt_punycode_links_einer_umlaut_domain():
    def antwort(r):
        if r.url.path == "/":
            return _html(f'<a href="https://{PUNY}/kontakt">Kontakt</a>')
        if r.url.path == "/kontakt":
            return _html("<title>Kontakt</title>")
        return httpx.Response(404)
    seiten = _crawlen("https://bäckerei-müller.de/", antwort)
    assert f"https://{PUNY}/kontakt" in seiten


# ---------- 2. Zeichensatz ----------

def test_zeichensatz_aus_meta_wenn_header_keinen_nennt():
    html = '<meta charset="iso-8859-1"><title>Bäckerei Müller</title>'.encode("latin-1")
    assert "Bäckerei Müller" in dekodieren(html, "text/html")
    assert "Größe" in dekodieren("Größe".encode("cp1252"), "text/html")          # ohne Angabe, kein UTF-8
    assert dekodieren("Größe".encode("utf-8"), "text/html") == "Größe"
    assert dekodieren("Größe".encode("latin-1"), "text/html; charset=ISO-8859-1") == "Größe"
    assert dekodieren(b"\xef\xbb\xbfok", None) == "ok"                             # BOM


def test_crawl_speichert_umlaute_einer_latin1_seite_richtig():
    inhalt = '<html><head><meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">' \
             '<title>Fahrräder in Köln</title></head></html>'
    seiten = _crawlen("https://k.de/", lambda r: httpx.Response(
        200, headers={"Content-Type": "text/html"}, content=inhalt.encode("latin-1")) if r.url.path == "/"
        else httpx.Response(404))
    assert seiten["https://k.de/"][1] == "Fahrräder in Köln"


# ---------- 3. robots.txt wie Google ----------

ROBOTS = """
User-agent: *
Disallow: /*?sort=
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
Disallow: /*.pdf$
Disallow:

User-agent: SeoToolBot
User-agent: Andererbot
Disallow: /nur-fuer-uns/

Sitemap: https://x.de/sitemap.xml
"""


def test_robots_platzhalter_vorrang_und_gruppen():
    r = RobotsTxt()
    r.parse(ROBOTS.splitlines())
    alle = "Irgendeinbot/1.0"
    assert not r.can_fetch(alle, "https://x.de/shop?sort=preis")              # * im Pfad
    assert r.can_fetch(alle, "https://x.de/shop?farbe=rot")
    assert not r.can_fetch(alle, "https://x.de/wp-admin/optionen")
    assert r.can_fetch(alle, "https://x.de/wp-admin/admin-ajax.php")          # längere Regel gewinnt
    assert not r.can_fetch(alle, "https://x.de/preise.pdf")                   # $ = Ende
    assert r.can_fetch(alle, "https://x.de/preise.pdf?v=2")
    # eigene Gruppe gilt statt „*“, auch wenn mehrere User-Agents sie teilen
    assert not r.can_fetch("SeoToolBot/0.1 (+lokal)", "https://x.de/nur-fuer-uns/a")
    assert r.can_fetch("SeoToolBot/0.1 (+lokal)", "https://x.de/wp-admin/optionen")
    assert r.site_maps() == ["https://x.de/sitemap.xml"]
    assert RobotsTxt().can_fetch(alle, "https://x.de/alles")                  # ohne robots.txt: alles erlaubt


def test_gleichstand_gewinnt_allow():
    r = RobotsTxt()
    r.parse(["User-agent: *", "Disallow: /seite", "Allow: /seite"])
    assert r.can_fetch("bot", "https://x.de/seite")


# ---------- 4. Große Dateien ----------

def test_pdf_wird_nicht_geladen_und_html_hat_obergrenze(monkeypatch):
    monkeypatch.setattr(crawler_modul, "MAX_HTML_BYTES", 1000)
    gelesen = {"pdf": False}

    class PdfStrom(httpx.SyncByteStream):
        def __iter__(self):
            gelesen["pdf"] = True
            yield b"%PDF" * 1000

    def antwort(r):
        if r.url.path == "/":
            return _html('<a href="/preise.pdf">PDF</a><a href="/riesig">Riesig</a>')
        if r.url.path == "/preise.pdf":
            return httpx.Response(200, headers={"Content-Type": "application/pdf", "Content-Length": "4000"},
                                  stream=PdfStrom())
        if r.url.path == "/riesig":
            return _html("<title>Riesig</title>" + "x" * 50_000)
        return httpx.Response(404)

    seiten = _crawlen("https://g.de/", antwort)
    assert not gelesen["pdf"]                                       # Inhalt nie gelesen
    assert seiten["https://g.de/preise.pdf"][2] == 4000             # Größe aus Content-Length
    assert seiten["https://g.de/riesig"][1] == "Riesig"             # Anfang reicht für Title
    assert seiten["https://g.de/riesig"][2] > 1000                  # echte Größe bleibt sichtbar


# ---------- 5. Timeouts und Bot-Sperren ----------

def test_timeout_dann_erfolg_zaehlt_nicht_als_nicht_erreichbar(monkeypatch):
    monkeypatch.setattr(crawler_modul, "WIEDERHOLEN_PAUSE", 0)
    versuche = {"/blog/": 0, "/faq/": 0}

    def antwort(r):
        if r.url.path == "/":
            return _html('<a href="/blog/">Blog</a><a href="/faq/">FAQ</a>')
        if r.url.path == "/blog/":           # erst Handshake-Timeout, dann Erfolg
            versuche["/blog/"] += 1
            if versuche["/blog/"] == 1:
                raise httpx.ConnectTimeout("_ssl.c:1063: The handshake operation timed out", request=r)
            return _html("<title>Blog</title>")
        if r.url.path == "/faq/":            # dauerhaft zu langsam
            versuche["/faq/"] += 1
            raise httpx.ReadTimeout("timed out", request=r)
        return httpx.Response(404)

    seiten = _crawlen("https://t.de/", antwort)
    assert seiten["https://t.de/blog/"][:2] == (200, "Blog")
    assert seiten["https://t.de/faq/"][0] is None
    assert versuche == {"/blog/": 2, "/faq/": 1 + crawler_modul.WIEDERHOLUNGEN}


def test_externer_link_mit_404_nur_fuer_bots_zaehlt_nicht():
    from app.checks.extern import externe_links_defekt
    anfragen = []

    def antwort(r):
        if r.url.host == "t.de":
            return _html('<a href="https://hilfe.example/antwort">Hilfe</a>'
                         '<a href="https://hilfe.example/weg">Alt</a>') if r.url.path == "/" else httpx.Response(404)
        anfragen.append((r.method, r.url.path, "Mozilla" in r.headers["user-agent"]))
        if r.url.path == "/antwort" and "Mozilla" in r.headers["user-agent"]:
            return httpx.Response(200)
        return httpx.Response(404)

    conn = verbinden()
    p = projekte.anlegen(conn, "t.de")
    crawl_id = conn.execute("INSERT INTO crawls (projekt_id, start_url) VALUES (?, ?)",
                            (p.id, "https://t.de/")).lastrowid
    conn.commit()
    client = httpx.Client(transport=httpx.MockTransport(antwort))
    Crawler(conn, crawl_id, CrawlEinstellungen(start_url="https://t.de/", crawl_delay=0), client).ausfuehren()

    status = dict(conn.execute("SELECT url, status_code FROM ressourcen WHERE crawl_id=? AND extern=1", (crawl_id,)))
    assert status == {"https://hilfe.example/antwort": 200, "https://hilfe.example/weg": 404}
    assert ("GET", "/antwort", True) in anfragen
    treffer = externe_links_defekt(conn, crawl_id)
    assert len(treffer) == 1 and "/weg" in str(treffer[0])
