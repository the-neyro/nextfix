"""On-Page SEO Checker: Seite lesen, Regeln, Semantik, Service (ohne Netz), UI/API."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import onpage, projekte
from app.db import verbinden
from app.keywords import suggest
from app.onpage import abgleich, ki, semantik
from app.onpage.seite import lesen

TEXT = " ".join(["Ein SEO Check zeigt Fehler auf der Website und hilft beim Ranking."] * 40)
GUT = f"""<!doctype html><html lang="de"><head><title>SEO Check kostenlos – Website prüfen | Ex</title>
<meta name="description" content="Kostenloser SEO Check: Website in 2 Minuten prüfen, Fehler finden und Ranking verbessern – mit klaren Tipps.">
<link rel="canonical" href="https://ex.de/seo-check/">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebPage","name":"x"}}</script></head>
<body><nav>Menü</nav><main><h1>SEO Check für deine Website</h1><p>{TEXT}</p>
<h2>Was prüft der SEO Check?</h2><p>Titel, Ladezeit und Links.</p><h2>Kosten und Ablauf</h2>
<img src="a.png" alt="SEO Check Ergebnis"></main></body></html>"""
SCHLECHT = """<html><head><title>Startseite</title><meta name="robots" content="noindex"></head>
<body><h1>Willkommen</h1><h1>Hallo</h1><p>Kurzer Text.</p><img src="b.png"></body></html>"""


def test_seite_lesen():
    s = lesen(GUT, "https://ex.de/seo-check/")
    assert s.title.startswith("SEO Check") and s.h1 == ["SEO Check für deine Website"]
    assert s.zwischen == ["Was prüft der SEO Check?", "Kosten und Ablauf"] and s.bilder == 1 and s.bilder_ohne_alt == 0
    assert "Menü" not in s.text and s.hat_hauptbereich and s.schema_typen == ["WebPage"]
    assert s.anfang.split()[:3] == ["SEO", "Check", "für"] and s.slug == "/seo-check/"


def test_treffer_tolerant():
    assert abgleich.phrase_in("seo check", "Der SEO-Check!") and abgleich.woerter_in("seo tool", "Die besten SEO-Tools")
    assert abgleich.woerter_in("größe prüfen", "Bildgroesse und Groesse pruefen")
    assert not abgleich.woerter_in("seo check", "Nur SEO hier")
    assert abgleich.kern("seo für anfänger") == ["seo", "anfaenger"] and abgleich.anzahl("seo check", TEXT) == 40


def test_regeln_gute_und_schlechte_seite():
    gut = abgleich.pruefen(lesen(GUT, "https://ex.de/seo-check/"), "seo check",
                           eingehend={"links": 5, "mit_keyword": 1}, vitals={"lcp": 1800, "cls": 0.01, "tbt": 50})
    offen = {p.id for p in gut if p.ok is False}
    assert offen == {"text_haeufigkeit", "lesbarkeit"}, offen  # 40× in 480 Wörtern; ein Absatz mit 480 Wörtern
    schlecht = abgleich.pruefen(lesen(SCHLECHT, "https://ex.de/"), "seo check")
    ids = {p.id: p for p in schlecht}
    assert all(ids[i].ok is False for i in ("title_keyword", "h1_keyword", "h1_eine", "indexierbar", "textlaenge", "bilder_alt"))
    assert "interne_links" not in ids and "vitals" not in ids  # ohne Crawl/Messung nicht bewertet
    assert ids["url_keyword"].ok is None  # Startseite: URL-Regel zählt nicht
    assert abgleich.score(schlecht) < 30 < abgleich.score(gut)
    assert all(p.tipp for p in schlecht if p.ok is False)


def test_textlaenge_an_mitbewerbern():
    s = lesen(GUT, "https://ex.de/seo-check/")
    p = {x.id: x for x in abgleich.pruefen(s, "seo check", mitbewerber_woerter=2000)}
    assert p["textlaenge"].ok is False and "1600" in p["textlaenge"].tipp


def test_semantik():
    vorschlaege = ["seo check kostenlos", "seo check online kostenlos", "seo check online", "was ist ein seo check",
                   "seo check für websites", "wie funktioniert seo check"]
    b = {x["begriff"]: x for x in semantik.aus_suggest(vorschlaege, "seo check", "SEO Check kostenlos und gratis")}
    assert b["kostenlos"]["auf_seite"] and not b["online"]["auf_seite"] and "fuer" not in b
    f = semantik.fragen(vorschlaege, "", ["Wie funktioniert der SEO Check?"], "seo check")
    assert {x["frage"]: x["beantwortet"] for x in f} == {"was ist ein seo check": False, "wie funktioniert seo check": True}
    m = semantik.aus_mitbewerbern(["Ladezeit prüfen und Ladezeit messen, Backlinks zählen",
                                   "Die Ladezeit messen hilft. Ladezeit messen!"], "seo check", "Nur Text ohne das")
    assert m[0]["begriff"] == "ladezeit messen" and all(x["begriff"] != "ladezeit" for x in m)


# ---------- Service ----------

SEITEN = {"https://ex.de/seo-check/": (200, GUT), "https://mb.de/a": (200, f"<main><p>{TEXT} Ladezeit messen</p></main>"),
          "https://mb.de/b": (200, f"<main><p>{TEXT} Ladezeit messen</p></main>")}


@pytest.fixture
def conn(monkeypatch):
    def holer(url, ua):
        if url not in SEITEN:
            raise onpage.OnpageFehler(f"{url} nicht erreichbar (ConnectError)")
        return SEITEN[url][0], SEITEN[url][1], url

    def antwort(request):
        q = request.url.params["q"]
        return httpx.Response(200, json=[q, [f"{q} online", f"{q} kostenlos", f"{q} online kostenlos"]])
    monkeypatch.setattr(onpage, "HOLER", holer)
    monkeypatch.setattr(onpage, "SUGGEST_FABRIK", lambda c, s, l: suggest.Suggest(
        c, s, l, client=httpx.Client(transport=httpx.MockTransport(antwort)), pause=0))
    c = verbinden()
    projekte.anlegen(c, "ex.de")
    return c


def test_service_mit_crawl_und_mitbewerbern(conn):
    cid = conn.execute("INSERT INTO crawls (projekt_id, start_url, status) VALUES (1, 'https://ex.de/', 'fertig')").lastrowid
    sid = conn.execute("INSERT INTO seiten (crawl_id, url, tiefe, status_code) VALUES (?, 'https://ex.de/seo-check/', 1, 200)",
                       (cid,)).lastrowid
    for anker in ["SEO Check", "mehr"]:
        conn.execute("INSERT INTO links (crawl_id, seite_id, ziel_url, art, intern, anker_text) VALUES (?, ?, ?, 'a', 1, ?)",
                     (cid, sid, "https://ex.de/seo-check/", anker))
    conn.commit()
    r = onpage.pruefen(conn, 1, "https://ex.de/seo-check/", "SEO Check",
                       ["https://mb.de/a", "https://mb.de/b", "https://weg.de/"])
    p = {x["id"]: x for x in r["pruefungen"]}
    assert p["interne_links"]["ok"] is False and p["interne_links"]["detail"] == "2 eingehende interne Links"
    assert p["anker_keyword"]["ok"] is True and r["hinweise"] == []
    assert [m.get("fehler", "")[:12] for m in r["mitbewerber"]] == ["", "", "https://weg."]
    assert r["begriffe_mitbewerber"][0]["begriff"] == "ladezeit messen"
    assert {b["begriff"] for b in r["begriffe_suggest"]} == {"online", "kostenlos"}
    assert r["ideen"] and r["ideen"][0]["prioritaet"] in ("hoch", "mittel")
    assert onpage.holen(conn, r["id"])["score"] == r["score"] and onpage.liste(conn, 1)[0]["keyword"] == "seo check"


def test_eingaben(conn):
    for url, kw, mb, text in [("ex.de", "seo", [], "http"), ("https://ex.de/", "x", [], "Keyword"),
                              ("https://ex.de/", "seo", ["https://a.de"] * 4, "Höchstens"),
                              ("https://ex.de/", "seo", ["a.de"], "Mitbewerber")]:
        with pytest.raises(onpage.OnpageFehler, match=text):
            onpage.pruefen(conn, 1, url, kw, mb)
    with pytest.raises(onpage.OnpageFehler, match="nicht erreichbar"):
        onpage.pruefen(conn, 1, "https://ex.de/fehlt", "seo")
    with pytest.raises(onpage.OnpageFehler, match="nicht gefunden"):
        onpage.holen(conn, 99)


def test_ui_und_api(conn):
    from app.web import app
    client = TestClient(app)
    assert "Seite optimieren" in client.get("/projekte/1/onpage").text
    r = client.post("/projekte/1/onpage", data={"url": "https://ex.de/seo-check/", "keyword": "seo check"})
    assert r.status_code == 200 and "Seiten-Score" in r.text and "Verbesserungen" in r.text and "KI-Score" in r.text
    assert "fehler" in client.post("/projekte/1/onpage", data={"url": "x", "keyword": "seo"}).text
    api = client.post("/api/projekte/1/onpage", json={"url": "https://ex.de/seo-check/", "keyword": "seo check",
                                                       "mit_suggest": False}).json()
    assert api["begriffe_suggest"] == [] and api["score"] > 0
    assert len(client.get("/api/projekte/1/onpage").json()) == 2
    assert "Seiten-Score" in client.get(f"/onpage/{api['id']}").text
    assert client.get("/onpage/999").status_code == 404


def test_mehrere_artikel_sind_nicht_der_hauptinhalt():
    """Startseite ohne <main> mit Teaser-Karten (<article>): ganzer Body zählt, nicht die erste Karte."""
    html = ("<body><header>Logo</header><h1>Start</h1><p>" + "Wort " * 300 + "</p>"
            + "<article><p>Karte eins kurz</p></article><article><p>Karte zwei</p></article></body>")
    s = lesen(html, "https://ex.de/")
    assert s.woerter > 300 and "Logo" not in s.text
    einzel = lesen("<body><nav>Menü</nav><article><p>Nur der Beitrag</p></article><p>Fuß</p></body>", "https://ex.de/b")
    assert einzel.text == "Nur der Beitrag"


def test_ki_score():
    gut = ki.pruefen(lesen(GUT, "https://ex.de/seo-check/"))
    p = {x.id: x.ok for x in gut}
    assert p["ki_hauptbereich"] and p["ki_gliederung"] and p["ki_fragen"] and p["ki_markup"]
    assert p["ki_zahlen"] is False and p["ki_quellen"] is False and p["ki_listen"] is False
    assert p["ki_faq_markup"] is None and p["ki_autor"] is None      # nur 1 Frage, kein Artikel
    schlecht = ki.bewerten(lesen(SCHLECHT, "https://ex.de/"))
    assert schlecht["score"] < abgleich.score(gut) and schlecht["score"] < 30
    # Gliederung/Listen zählen bei kurzem Text nicht
    assert {x["id"]: x["ok"] for x in schlecht["pruefungen"]}["ki_gliederung"] is None


def test_vorschlag_fuer_title_und_h1():
    assert abgleich.title_vorschlag("ki agentur", "Radhaus – Digitale Lösungen") == "KI Agentur: Digitale Lösungen | Radhaus"
    assert abgleich.title_vorschlag("seo check", "Startseite") == "SEO Check"
    lang = abgleich.title_vorschlag("on premise ki", "On-Premise KI vs. Cloud: Was ist besser für Unternehmen im Mittelstand? – Radhaus")
    assert lang == "On Premise KI | Radhaus" and len(lang) <= abgleich.TITLE_MAX
    p = {x.id: x for x in abgleich.pruefen(lesen(SCHLECHT, "https://ex.de/"), "seo check")}
    assert p["title_keyword"].vorschlag == "SEO Check" and p["h1_keyword"].vorschlag == "SEO Check: Willkommen"
