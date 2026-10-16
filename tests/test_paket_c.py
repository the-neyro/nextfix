"""Checks aus Paket C (hreflang, KI, Duplicate Content, Markup, Technik) direkt auf vorbereiteten DB-Zeilen."""

import json

import pytest

from app.checks import REGISTER
from app.core import projekte
from app.crawler.texte import signatur
from app.db import verbinden

B = "https://ex.de/"


@pytest.fixture
def db():
    conn = verbinden()
    p = projekte.anlegen(conn, "ex.de")
    crawl_id = conn.execute("INSERT INTO crawls (projekt_id, start_url) VALUES (?, ?)", (p.id, B)).lastrowid
    return conn, crawl_id


def seite(conn, crawl_id, pfad, status=200, **felder):
    """Seite einfügen; JSON-Felder als Python-Objekte übergeben."""
    werte = {"url": B + pfad, "tiefe": 1, "status_code": status, "woerter": 300, "lang": "de",
             "last_modified": "Tue, 13 Oct 2026 10:00:00 GMT"}
    werte.update({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in felder.items()})
    spalten = ", ".join(werte)
    conn.execute(f"INSERT INTO seiten (crawl_id, {spalten}) VALUES (?{', ?' * len(werte)})", (crawl_id, *werte.values()))


def treffer(conn, crawl_id, check_id) -> dict[str, str | None]:
    """{pfad: detail} der Treffer eines Checks."""
    urls = dict(conn.execute("SELECT id, url FROM seiten WHERE crawl_id=?", (crawl_id,)))
    return {(urls[s][len(B):] if s else "SITE"): d for s, d in REGISTER[check_id].funktion(conn, crawl_id)}


def hl(*paare, absolut=True):
    return [{"lang": lang, "url": B + pfad, "absolut": absolut} for lang, pfad in paare]


def test_hreflang_sauber(db):
    conn, c = db
    seite(conn, c, "de", hreflang=hl(("de", "de"), ("en", "en"), ("x-default", "de")))
    seite(conn, c, "en", lang="en", hreflang=hl(("de", "de"), ("en", "en"), ("x-default", "de")))
    for check_id in ("hreflang_code_ungueltig", "hreflang_relativ", "hreflang_ohne_selbstbezug", "hreflang_doppelt",
                     "hreflang_ziel_defekt", "hreflang_ohne_rueckverweis", "hreflang_lang_konflikt"):
        assert treffer(conn, c, check_id) == {}, check_id


def test_hreflang_fehler(db):
    conn, c = db
    seite(conn, c, "a", hreflang=hl(("de", "a"), ("english", "b"), ("fr", "weg"), ("fr", "c")))
    seite(conn, c, "b", lang="en", hreflang=hl(("en", "b")))          # kein Rückverweis auf a
    seite(conn, c, "c", lang="fr", hreflang=hl(("de", "a"), absolut=False))   # relativ, ohne Selbstbezug
    seite(conn, c, "weg", status=404)
    seite(conn, c, "d", lang="en", hreflang=hl(("de", "d")))          # lang widerspricht
    assert treffer(conn, c, "hreflang_code_ungueltig") == {"a": "english"}
    assert set(treffer(conn, c, "hreflang_relativ")) == {"c"}
    assert set(treffer(conn, c, "hreflang_ohne_selbstbezug")) == {"c"}
    assert treffer(conn, c, "hreflang_doppelt") == {"a": "fr"}
    assert treffer(conn, c, "hreflang_ziel_defekt") == {"a": B + "weg (404)"}
    assert treffer(conn, c, "hreflang_ohne_rueckverweis") == {"a": B + "b"}   # c verweist zurück
    assert treffer(conn, c, "hreflang_lang_konflikt") == {"d": "lang=en, hreflang=de"}


def test_duplicate_content(db):
    conn, c = db
    text = " ".join(f"wort{i}" for i in range(300))
    anders = " ".join(f"anders{i}" for i in range(300))
    seite(conn, c, "eins", signatur=signatur(text))
    seite(conn, c, "zwei", signatur=signatur(text + " ein paar neue worte am ende"))
    seite(conn, c, "drei", signatur=signatur(anders))
    seite(conn, c, "variante", signatur=signatur(text), canonical=B + "eins")   # gewollte Variante
    t = treffer(conn, c, "duplicate_content")
    assert set(t) == {"eins", "zwei"}
    assert t["eins"].endswith("wie " + B + "zwei")


def test_ki_markup_technik(db):
    conn, c = db
    seite(conn, c, "gut", semantik=["main", "nav"], lesbarkeit=[], markup={"typen": ["Product"], "fehler": []},
          plugins=[], kaputte_links=[], hat_passwort=1)
    seite(conn, c, "alt", semantik=["nav"], lesbarkeit=["Lange Sätze (Ø 30 Wörter)"],
          markup={"typen": [], "fehler": ["Product: Pflichtfeld(er) fehlen: name"]},
          plugins=["object", "embed"], kaputte_links=["http:/x.de", "htp://y"], last_modified=None)
    conn.execute("UPDATE seiten SET url='http://ex.de/login' WHERE url=?", (B + "gut",))
    conn.execute("INSERT INTO seiten (crawl_id, url, tiefe, status_code, woerter, hat_passwort) VALUES (?, ?, 1, 200, 50, 1)",
                 (c, B + "login-https"))
    assert set(treffer(conn, c, "ki_ohne_hauptbereich")) == {"alt"}
    assert treffer(conn, c, "ki_schwer_lesbar") == {"alt": "Lange Sätze (Ø 30 Wörter)"}
    assert treffer(conn, c, "markup_fehlerhaft") == {"alt": "Product: Pflichtfeld(er) fehlen: name"}
    assert treffer(conn, c, "veraltete_plugins") == {"alt": "embed, object"}
    assert treffer(conn, c, "link_syntax_fehler") == {"alt": "2×, z. B. http:/x.de"}
    assert treffer(conn, c, "ohne_last_modified") == {"SITE": "2 von 3 HTML-Seiten"}
    passwort = REGISTER["passwort_ohne_https"].funktion(conn, c)
    assert [conn.execute("SELECT url FROM seiten WHERE id=?", (s,)).fetchone()[0] for s, _ in passwort] == ["http://ex.de/login"]


@pytest.mark.parametrize("href, kaputt", [
    ("tel:+4940756 81783", False),   # Fehlalarm auf einer echten Website
    ("mailto:a@b.de", False), ("#oben", False), ("/seite", False), ("https://ex.de/a", False),
    ("http:/ex.de", True), ("http//ex.de", True), ("htp://ex.de", True), ("/mit leerzeichen", True), ("https://", True),
])
def test_kaputter_link(href, kaputt):
    from app.crawler.parser import kaputter_link
    assert kaputter_link(href) is kaputt


# ---------- Paket D ----------

@pytest.mark.parametrize("cache_control, expires, gecacht", [
    ("public, max-age=31536000", None, True), ("max-age=0", None, False), ("no-cache", None, False),
    ("no-store, max-age=600", None, False), (None, "Thu, 01 Jan 2027 00:00:00 GMT", True), (None, None, False),
    ("public, immutable", None, True),
])
def test_wird_gecacht(cache_control, expires, gecacht):
    from app.crawler.ressourcen import wird_gecacht
    assert wird_gecacht(cache_control, expires) is gecacht


def test_ist_minifiziert():
    from app.crawler.ressourcen import ist_minifiziert
    assert ist_minifiziert("a{b:c}") is None
    assert ist_minifiziert("function f(){return 1}" * 200) is True
    assert ist_minifiziert("function f() {\n    return 1;\n}\n" * 120) is False
    assert ist_minifiziert(".a{color: red;}\n" * 200) is True        # wie style.min.css einer echten Website (Fehlalarm)
    assert ist_minifiziert("/* Erklärung der Regel */\n.a{color:red}\n" * 100) is False
    assert ist_minifiziert("/*! Lizenz MIT */\n" + ".a{color:red}\n" * 200) is True


def test_js_css_checks(db):
    conn, c = db
    seite(conn, c, "a")
    seite(conn, c, "b")
    ids = dict(conn.execute("SELECT url, id FROM seiten WHERE crawl_id=?", (c,)))
    dateien = [  # url, art, extern, status, bytes, encoding, gecacht, minifiziert
        ("app.js", "script", 0, 200, 1_500_000, None, 0, 0),
        ("gut.css", "css", 0, 200, 900_000, "br", 1, 1),
        ("cdn.js", "script", 1, 404, None, None, None, None),
    ]
    for url, art, extern, status, bytes_, enc, cache, mini in dateien:
        conn.execute("INSERT INTO ressourcen VALUES (?,?,?,?,?,?,?,?,?)", (c, B + url, art, status, extern, bytes_, enc, cache, mini))
        conn.execute("INSERT INTO links (crawl_id, seite_id, ziel_url, art, intern) VALUES (?,?,?,?,?)",
                     (c, ids[B + "a"], B + url, art, 1 - extern))
    conn.execute("INSERT INTO links (crawl_id, seite_id, ziel_url, art, intern) VALUES (?,?,?,?,1)", (c, ids[B + "b"], B + "gut.css", "css"))
    assert treffer(conn, c, "js_css_zu_gross") == {"a": "2343 KB"}
    assert set(treffer(conn, c, "js_css_unkomprimiert")) == {"a"}
    assert set(treffer(conn, c, "js_css_ohne_cache")) == {"a"}
    assert treffer(conn, c, "js_css_nicht_minifiziert") == {"a": f"1 Datei(en), z. B. {B}app.js"}
    assert treffer(conn, c, "externe_js_css_defekt") == {"a": f"{B}cdn.js (404)"}
    assert treffer(conn, c, "interne_js_css_defekt") == {}
    assert treffer(conn, c, "zu_viele_js_css") == {}


def test_meta_description_laenge():
    from app.checks import inhalt
    conn = verbinden()
    p = projekte.anlegen(conn, "md.de").id
    c = conn.execute("INSERT INTO crawls (projekt_id, start_url, status) VALUES (?, 'https://md.de/', 'fertig')",
                     (p,)).lastrowid
    for i, laenge in enumerate([0, 42, 69, 70, 160, 161, 248]):
        conn.execute("INSERT INTO seiten (crawl_id, url, tiefe, status_code, woerter, meta_description)"
                     " VALUES (?, ?, 1, 200, 300, ?)", (c, f"https://md.de/{i}", "x" * laenge or None))
    lang = [d for _, d in inhalt.meta_desc_zu_lang(conn, c)]
    kurz = [d for _, d in inhalt.meta_desc_zu_kurz(conn, c)]
    assert sorted(lang) == ["161 Zeichen", "248 Zeichen"] and sorted(kurz) == ["42 Zeichen", "69 Zeichen"]
