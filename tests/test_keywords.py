"""Phase 5: Keyword-Recherche (Suggest nachgebaut, Intent, Gruppen, GSC-Anreicherung, UI)."""

import time
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import export, keywords, positionen, projekte
from app.db import verbinden
from app.keywords import analyse, suggest


class FakeSuggest:
    """Antwortet wie Google Suggest (client=firefox). status: erzwungener Fehler ab Anfrage Nr. `ab`."""

    def __init__(self, status=None, ab=0):
        self.status, self.ab = status, ab
        self.anfragen = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        self.anfragen.append(q)
        assert request.url.params["hl"] == "de" and request.url.params["client"] == "firefox"
        if self.status and len(self.anfragen) > self.ab:
            return httpx.Response(self.status)
        return httpx.Response(200, json=[q, [q, f"{q} kostenlos", f"{q} test", f"was ist {q}", "Völlig  Anderes"]])


@pytest.fixture
def fake(monkeypatch):
    f = FakeSuggest()
    monkeypatch.setattr(keywords, "SUGGEST_FABRIK", lambda conn, s, l: suggest.Suggest(
        conn, s, l, client=httpx.Client(transport=httpx.MockTransport(f)), pause=0))
    return f


@pytest.fixture
def conn():
    c = verbinden()
    projekte.anlegen(c, "ex.de")
    return c


# ---------- Bausteine ----------

def test_erweiterungen():
    e = suggest.erweiterungen("  SEO  Tool ")
    assert e[0] == "seo tool" and "seo tool a" in e and "seo tool z" in e and "was ist seo tool" in e
    assert "seo tool kostenlos" in e and len(e) == len(set(e)) == 47


@pytest.mark.parametrize("keyword, erwartet", [
    ("seo tool kaufen", "transaktional"), ("seo tool preis", "transaktional"),
    ("seo tool login", "navigational"), ("ex", "navigational"), ("ex seo tool anleitung", "informational"),
    ("seo tool test", "kommerziell"), ("beste seo tools", "kommerziell"), ("seo tool vs semrush", "kommerziell"),
    ("was ist ein seo tool", "informational"), ("seo tool", "informational"),
    ("best seo tool", "kommerziell"), ("buy seo tool", "transaktional"), ("seo check website", "informational"),
])
def test_intent(keyword, erwartet):
    assert analyse.intent(keyword, marke="ex") == erwartet


def test_lesbar():
    assert analyse.lesbar("seo prüfen größe") and analyse.lesbar("seo-check 2026 & co.")
    assert not analyse.lesbar("check seo bài viết") and not analyse.lesbar("seo проверка")


def test_frage_und_gruppen():
    assert analyse.ist_frage("wie funktioniert seo") and analyse.ist_frage("seo sinnvoll?")
    assert not analyse.ist_frage("seo tool kostenlos")
    g = analyse.gruppieren(["seo tool", "seo tool kostenlos", "kostenlos seo tool online", "seo tool test",
                            "seo tool test vergleich", "seo tool für wordpress"], "seo tool")
    assert g["seo tool"] == "(Hauptbegriff)"
    assert g["seo tool kostenlos"] == g["kostenlos seo tool online"] == "kostenlos"
    assert g["seo tool test"] == g["seo tool test vergleich"] == "test"
    assert g["seo tool für wordpress"] == "sonstige"  # einzelne Gruppe


def test_suggest_cache_und_pause(conn):
    f = FakeSuggest()
    s = suggest.Suggest(conn, client=httpx.Client(transport=httpx.MockTransport(f)), pause=0.05)
    start = time.monotonic()
    assert s.vorschlaege("seo")[1] == "seo kostenlos"
    s.vorschlaege("seo b")
    assert time.monotonic() - start >= 0.05  # Pause zwischen echten Anfragen
    assert s.vorschlaege("seo")[-1] == "völlig anderes"  # aus dem Cache, normalisiert
    assert f.anfragen == ["seo", "seo b"] and s.anfragen_echt == 2


@pytest.mark.parametrize("status, text", [(429, "bremst"), (403, "bremst"), (500, "500")])
def test_suggest_fehler(conn, status, text):
    s = suggest.Suggest(conn, client=httpx.Client(transport=httpx.MockTransport(FakeSuggest(status))), pause=0)
    with pytest.raises(suggest.SuggestFehler, match=text):
        s.vorschlaege("seo")


# ---------- Recherche ----------

def test_recherche_mit_gsc_daten(conn, fake):
    positionen.importieren(conn, 1, "mock", 30, bis=date(2026, 10, 1))
    r = keywords.starten(conn, 1, "SEO Check", warten=True)
    r = keywords.holen(conn, r["id"])
    assert (r["status"], r["schritte_fertig"], r["schritte_gesamt"]) == ("fertig", 47, 47)
    d = keywords.ideen(conn, r["id"], limit=1000)
    alle = {i["keyword"]: i for i in d["ideen"]}
    assert "völlig anderes" not in alle  # ohne Wort des Hauptbegriffs verworfen
    assert alle["seo check kostenlos"]["intent"] == "kommerziell" and alle["seo check"]["intent"] == "informational"
    assert alle["was ist seo check"]["frage"] is True
    # Mock-GSC enthält „seo check“ (und weitere Begriffe mit „seo“) → angereichert
    assert set(alle["seo check"]["quellen"]) == {"gsc", "suggest"} and alle["seo check"]["gsc_impressionen"] > 0
    assert any(i["quellen"] == ["gsc"] for i in d["ideen"])
    assert d["ideen"][0]["gsc_impressionen"] == max(i["gsc_impressionen"] or 0 for i in d["ideen"])
    assert sum(g["anzahl"] for g in d["gruppen"]) == r["ideen"] == d["gesamt"]
    assert keywords.ideen(conn, r["id"], nur_fragen=True)["gesamt"] == d["fragen"] > 0
    assert keywords.ideen(conn, r["id"], intent="kommerziell")["gesamt"] == d["intents"]["kommerziell"]
    # Wiederholung: alles aus dem Cache
    vorher = len(fake.anfragen)
    keywords.starten(conn, 1, "seo check", warten=True)
    assert len(fake.anfragen) == vorher


def test_recherche_abbruch_behaelt_teilergebnis(conn, monkeypatch):
    f = FakeSuggest(status=429, ab=3)
    monkeypatch.setattr(keywords, "SUGGEST_FABRIK", lambda c, s, l: suggest.Suggest(
        c, s, l, client=httpx.Client(transport=httpx.MockTransport(f)), pause=0))
    r = keywords.holen(conn, keywords.starten(conn, 1, "seo", warten=True)["id"])
    assert r["status"] == "fehler" and "bremst" in r["fehler_text"] and r["schritte_fertig"] == 3
    assert keywords.ideen(conn, r["id"])["gesamt"] > 3


def test_eingaben_und_paralleler_lauf(conn, fake):
    with pytest.raises(keywords.KeywordFehler):
        keywords.starten(conn, 1, " a ")
    conn.execute("INSERT INTO recherchen (projekt_id, seed, lebenszeichen) VALUES (1, 'x', datetime('now'))")
    conn.commit()
    with pytest.raises(keywords.KeywordFehler, match="läuft noch"):
        keywords.starten(conn, 1, "seo")
    with pytest.raises(keywords.KeywordFehler, match="Sortierung"):
        keywords.ideen(conn, 1, sortierung="quatsch")
    with pytest.raises(keywords.KeywordFehler, match="nicht gefunden"):
        keywords.holen(conn, 99)


def test_csv(conn, fake):
    rid = keywords.starten(conn, 1, "seo", warten=True)["id"]
    text = export.recherche_csv(conn, rid, intent="kommerziell")
    zeilen = text.lstrip("﻿").splitlines()
    assert zeilen[0].startswith("Keyword;Intent;Gruppe") and all(";kommerziell;" in z for z in zeilen[1:])


# ---------- REST und UI ----------

def test_ui_und_api(fake):
    from app.web import app
    client = TestClient(app)
    p = client.post("/api/projekte", json={"domain": "ex.de"}).json()["id"]
    assert "Suchbegriffe finden" in client.get(f"/projekte/{p}/keywords").text
    r = client.post(f"/projekte/{p}/keywords", data={"seed": "seo tool"})
    assert r.status_code == 200 and 'id="recherchen"' in r.text
    ende = time.time() + 10
    while client.get(f"/api/projekte/{p}/keywords/recherchen").json()[0]["status"] == "laeuft":
        assert time.time() < ende
        time.sleep(0.05)
    rid = client.get(f"/api/projekte/{p}/keywords/recherchen").json()[0]["id"]
    seite = client.get(f"/recherchen/{rid}?intent=informational").text
    assert "Gruppen" in seite and 'value="was ist seo tool"' in seite and 'value="seo tool test"' not in seite
    # Ankreuzen → Tracking-Liste, zurück zur Recherche
    r = client.post(f"/projekte/{p}/tracking", data={"aktion": "hinzufuegen", "query": ["seo tool test"],
                                                       "zurueck": f"/recherchen/{rid}"}, follow_redirects=False)
    assert r.headers["location"] == f"/recherchen/{rid}"
    assert 'title="wird beobachtet"' in client.get(f"/recherchen/{rid}").text
    api = client.get(f"/api/keywords/recherchen/{rid}?nur_fragen=true").json()
    assert api["gesamt"] == api["fragen"] > 0
    assert client.get(f"/api/keywords/recherchen/{rid}/ideen.csv").text.startswith("﻿Keyword")
    assert client.post(f"/api/projekte/{p}/keywords/recherchen", json={"seed": "x"}).status_code == 400
    assert client.delete(f"/api/keywords/recherchen/{rid}").status_code == 204
    assert client.get(f"/recherchen/{rid}").status_code == 404


def test_nische_mit_teilphrasen(conn, monkeypatch):
    """Liefert der Hauptbegriff kaum Vorschläge, werden Teilphrasen mit dem längsten Wort nachgefragt."""
    assert suggest.teilphrasen("ki agentur hamburg") == ["ki agentur", "agentur hamburg"]
    assert suggest.teilphrasen("webagentur hamburg") == ["webagentur"] and suggest.teilphrasen("seo") == []

    def antwort(request):
        q = request.url.params["q"]
        if "webagentur hamburg" in q:  # wie echtes Google bei Nischen-Begriffen: fast nichts
            return httpx.Response(200, json=[q, [q] if q == "webagentur hamburg" else []])
        return httpx.Response(200, json=[q, [f"{q} preise", "webagentur hamburg altona", "hamburg hafen"]])
    monkeypatch.setattr(keywords, "SUGGEST_FABRIK", lambda c, s, l: suggest.Suggest(
        c, s, l, client=httpx.Client(transport=httpx.MockTransport(antwort)), pause=0))
    r = keywords.holen(conn, keywords.starten(conn, 1, "webagentur hamburg", warten=True)["id"])
    assert r["schritte_gesamt"] == 47 + 27 and r["schritte_fertig"] == 74
    ideen = {i["keyword"] for i in keywords.ideen(conn, r["id"], limit=1000)["ideen"]}
    assert {"webagentur preise", "webagentur hamburg altona"} <= ideen and "hamburg hafen" not in ideen
