"""GEO / KI-Suche: Signale aus dem Parser, llms.txt-Auswertung und die Checks dazu."""

import json

from app.crawler.parser import zerlegen
from app.crawler.site import llms_auswerten
from tests.test_paket_c import db, seite, treffer  # noqa: F401  (db ist eine Fixture)

ARTIKEL = """<html><head><meta property="og:type" content="article">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","headline":"x",
"datePublished":"2026-01-01"}</script></head>
<body><nav><a href="https://facebook.com/ex">fb</a> 50 % Rabatt</nav>
<main><h2>Was kostet das?</h2><p>Es kostet 30 % weniger, laut <a href="https://www.destatis.de/x">Destatis</a>
und <a href="https://ex.de/intern">intern</a>.</p><h3>Wie lange dauert es?</h3><ul><li>a</li></ul></main></body></html>"""


def test_geo_signale_aus_parser():
    g = zerlegen(ARTIKEL, "https://www.ex.de/a").geo
    assert g["artikel"] and g["datum"] and not g["autor"]
    assert g["fragen"] == 2 and g["zwischen"] == 2 and g["listen"] == 1
    assert g["zahlen"] == 1      # „50 %“ steht in der Navigation, zählt nicht
    assert g["quellen"] == 1     # destatis.de; ex.de ist intern (auch ohne www.), facebook in nav


def test_geo_ohne_artikel_und_jahreszahl_ist_keine_statistik():
    g = zerlegen("<html><body><main><p>Seit 2019 in Hamburg.</p></main></body></html>", "https://ex.de/").geo
    assert not g["artikel"] and g["zahlen"] == 0 and g["quellen"] == 0


def test_llms_auswerten():
    l = llms_auswerten("# Ex\n\n> Kurz.\n\n## Docs\n- [A](/a): x\n- [B](https://ex.de/b)\n", "https://ex.de/llms.txt")
    assert l == {"format_ok": True, "zusammenfassung": True, "abschnitte": 1,
                 "links": ["https://ex.de/a", "https://ex.de/b"], "links_anzahl": 2}


def test_llms_nackte_urls():
    l = llms_auswerten("# Ex\n- Leistung, https://ex.de/l\n  Text.\n- Kontakt: https://ex.de/k.\n- [A](https://ex.de/l)\n",
                       "https://ex.de/llms.txt")
    assert l["links"] == ["https://ex.de/l", "https://ex.de/k"]


def geo(**werte):
    basis = {"artikel": False, "datum": False, "autor": False, "woerter": 100, "zahlen": 0, "quellen": 0,
             "fragen": 0, "listen": 0, "zwischen": 0}
    return {**basis, **werte}


def test_geo_checks(db):
    conn, c = db
    seite(conn, c, "", tiefe=0, geo=geo(), markup={"typen": ["WebSite"], "fehler": []})
    seite(conn, c, "faq", geo=geo(fragen=3), markup={"typen": [], "fehler": []})
    seite(conn, c, "faq-ok", geo=geo(fragen=3), markup={"typen": ["FAQPage"], "fehler": []})
    seite(conn, c, "leer", geo=geo(woerter=400))
    seite(conn, c, "belegt", geo=geo(woerter=400, quellen=2))
    seite(conn, c, "wand", geo=geo(woerter=800, zahlen=1, zwischen=1))
    seite(conn, c, "gegliedert", geo=geo(woerter=800, zahlen=1, listen=2))
    seite(conn, c, "artikel", geo=geo(artikel=True, autor=True))
    seite(conn, c, "artikel-ok", geo=geo(artikel=True, autor=True, datum=True))
    assert treffer(conn, c, "ki_fragen_ohne_faq") == {"faq": "3 Fragen"}
    assert treffer(conn, c, "ki_ohne_belege") == {"leer": "400 Wörter"}
    assert treffer(conn, c, "ki_textwand") == {"wand": "800 Wörter, 1 Zwischenüberschriften"}
    assert treffer(conn, c, "ki_artikel_ohne_autor_datum") == {"artikel": "fehlt: Datum"}
    assert treffer(conn, c, "ki_ohne_entitaet") == {"": "WebSite"}


def test_entitaet_vorhanden(db):
    conn, c = db
    seite(conn, c, "", tiefe=0, geo=geo(), markup={"typen": ["WebSite", "Organization"], "fehler": []})
    assert treffer(conn, c, "ki_ohne_entitaet") == {}


def fakten_setzen(conn, c, llms):
    conn.execute("UPDATE crawls SET fakten=? WHERE id=?", (json.dumps({"llms": llms}), c))


def test_llms_duenn_und_tote_links(db):
    conn, c = db
    seite(conn, c, "a")
    seite(conn, c, "weg", status=404)
    seite(conn, c, "gesperrt", status=None, blockiert=1)
    llms = {"status": 200, "format_ok": True, **llms_auswerten(
        "# Ex\n- [A](/a)\n- [W](/weg)\n- [G](/gesperrt)\n- [W2](/weg)\n", "https://ex.de/llms.txt")}
    fakten_setzen(conn, c, llms)
    assert treffer(conn, c, "llms_duenn") == {"SITE": "keine Kurzbeschreibung"}
    assert treffer(conn, c, "llms_tote_links") == {"SITE": "https://ex.de/weg (404)"}


def test_llms_alte_fakten_ohne_inhalt(db):
    conn, c = db
    fakten_setzen(conn, c, {"status": 200, "format_ok": True})  # Crawl vor GEO-Ausbau
    assert treffer(conn, c, "llms_duenn") == {} and treffer(conn, c, "llms_tote_links") == {}


def test_rechtsseiten_ohne_belege_ausgenommen(db):
    from app.checks.ki import ist_rechtsseite
    assert ist_rechtsseite("https://ex.de/agb/") and ist_rechtsseite("https://ex.de/de/datenschutzerklaerung")
    assert ist_rechtsseite("https://ex.de/impressum.html") and ist_rechtsseite("https://ex.de/cookie-richtlinie")
    assert not ist_rechtsseite("https://ex.de/blog-datenschutz-ki") and not ist_rechtsseite("https://ex.de/")
    conn, c = db
    seite(conn, c, "agb", geo=geo(woerter=900))
    seite(conn, c, "ratgeber", geo=geo(woerter=900))
    assert treffer(conn, c, "ki_ohne_belege") == {"ratgeber": "900 Wörter"}


def test_training_bots_nur_hinweis(db):
    conn, c = db
    robots = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: CCBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    conn.execute("UPDATE crawls SET robots_status=200, robots_text=?, start_url='https://ex.de/' WHERE id=?",
                 (robots, c))
    assert treffer(conn, c, "ki_training_bots_blockiert") == {"SITE": "GPTBot, CCBot"}
    assert treffer(conn, c, "ki_bots_blockiert") == {}


def test_wenig_text_zaehlt_nur_hauptinhalt(db):
    """Abgleich mit externem Audit: Glossar mit ~150 Wörtern Text, aber 330 mit Menü/Fuß."""
    conn, c = db
    seite(conn, c, "glossar", woerter=330, geo=geo(woerter=150))
    seite(conn, c, "ratgeber", woerter=900, geo=geo(woerter=700))
    seite(conn, c, "alt", woerter=120)            # alter Crawl ohne GEO-Signale
    assert treffer(conn, c, "wenig_text") == {"glossar": "150 Wörter", "alt": "120 Wörter"}


def test_render_blockierende_skripte(db):
    html = """<html><head><script src="/a.js"></script><script src="/b.js" defer></script>
    <script src="/c.js" async></script><script type="module" src="/d.js"></script><script>inline()</script></head>
    <body><script src="/unten.js"></script></body></html>"""
    assert zerlegen(html, "https://ex.de/").blockierend == ["/a.js"]
    conn, c = db
    seite(conn, c, "langsam", blockierend=["/js/jquery.min.js", "/js/chat.js"])
    seite(conn, c, "schnell", blockierend=[])
    assert treffer(conn, c, "skripte_blockierend") == {"langsam": "2: jquery.min.js, chat.js"}
