"""Fehler, die der Prüfstand (scripts/pruefstand.py) gefunden hat: je ein schneller Test pro Fix."""

from app.checks.site import robots_pruefen
from app.crawler.markup import jsonld_auswerten
from app.crawler.parser import zerlegen
from app.crawler.robots import RobotsTxt
from app.crawler.site import llms_auswerten
from app.crawler.vitals import BEOBACHTER_JS
from tests.test_paket_c import B, db, hl, seite, treffer  # noqa: F401  (db ist eine Fixture)


def test_h1_gleich_title_auch_mit_umlauten(db):
    conn, c = db
    seite(conn, c, "a", title="Über uns", h1_anzahl=1, h1_text="über uns")
    seite(conn, c, "b", title="Über uns", h1_anzahl=1, h1_text="Über unser Team")
    assert set(treffer(conn, c, "h1_gleich_title")) == {"a"}


def test_bom_am_anfang_von_robots_und_llms():
    robots = RobotsTxt()
    robots.parse("﻿User-agent: *\nDisallow: /intern/\n".splitlines())
    assert not robots.can_fetch("SeoToolBot/0.1", "https://ex.de/intern/x")
    assert robots_pruefen("﻿User-agent: *\nDisallow: /intern/\n") == []
    assert llms_auswerten("﻿# Name\n\n> Kurz.\n", "https://ex.de/llms.txt")["format_ok"]


def test_markup_wie_google():
    artikel = '{"@context":"https://schema.org","@type":"BlogPosting","author":{"@type":"Person","name":"M"}}'
    assert jsonld_auswerten([artikel])["fehler"] == []   # Article hat keine Pflichtfelder
    nur_name = '{"@context":"https://schema.org","@type":"Product","name":"Rad"}'
    assert jsonld_auswerten([nur_name])["fehler"] == ["Product: eines dieser Felder fehlt: offers, review, aggregateRating"]
    mit_angebot = '{"@context":"https://schema.org","@type":"Product","name":"Rad","offers":{"price":"1"}}'
    assert jsonld_auswerten([mit_angebot])["fehler"] == []


def test_doctype_nach_kommentar():
    assert zerlegen("<!-- CMS -->\n<!DOCTYPE html><html><body></body></html>", B).hat_doctype
    assert not zerlegen("<!-- CMS --><html><body></body></html>", B).hat_doctype


def test_plugins_nicht_am_dateinamen():
    pdf = zerlegen('<body><object data="/java-kurs.pdf" type="application/pdf"></object></body>', B)
    flash = zerlegen('<body><object data="/film.swf"></object><applet code="A"></applet></body>', B)
    assert pdf.plugins == [] and flash.plugins == ["object", "applet"]


def test_robots_none_und_googlebot_sind_noindex():
    assert "noindex" in zerlegen('<head><meta name="robots" content="none"></head>', B).meta_robots
    assert "noindex" in zerlegen('<head><meta name="googlebot" content="noindex"></head>', B).meta_robots
    assert "noindex" not in zerlegen('<head><meta name="robots" content="noimageindex"></head>', B).meta_robots


def test_perm_redirect_nur_bei_internem_link(db):
    conn, c = db
    seite(conn, c, "start")
    seite(conn, c, "alt", status=301, redirect_ziel=B + "zwischen")
    seite(conn, c, "zwischen", status=301, redirect_ziel=B + "neu")
    start = conn.execute("SELECT id FROM seiten WHERE url=?", (B + "start",)).fetchone()[0]
    conn.execute("INSERT INTO links (crawl_id, seite_id, ziel_url, art, intern) VALUES (?, ?, ?, 'a', 1)",
                 (c, start, B + "alt"))
    assert set(treffer(conn, c, "perm_redirect")) == {"alt"}


def test_hreflang_rueckverweis_fehlt_wenn_ziel_gar_kein_hreflang_hat(db):
    conn, c = db
    seite(conn, c, "de", hreflang=hl(("de", "de"), ("en", "en")))
    seite(conn, c, "en", lang="en")
    assert treffer(conn, c, "hreflang_ohne_rueckverweis") == {"de": B + "en"}


def test_cls_ignoriert_phantom_eingabe_der_handy_emulation():
    assert "if (e.hadRecentInput) continue" not in BEOBACHTER_JS   # echter Browser-Fall: Prüfstand /cls-springt
