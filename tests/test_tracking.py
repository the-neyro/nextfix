"""Phase 4: Tracking-Liste (Begriffe wählen, Tags, Einfluss auf die Kennzahlen)."""

import pytest
from fastapi.testclient import TestClient

from app.core import positionen, projekte, tracking
from app.db import verbinden
from tests.test_positionen import FesteQuelle, laden, zeile  # noqa: F401 (Fixture-Helfer)


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setitem(positionen.gsc.QUELLEN, "fest", FesteQuelle)
    monkeypatch.setitem(positionen.gsc.SUCHMASCHINE, "fest", "google")
    c = verbinden()
    projekte.anlegen(c, "ex.de")
    return c


def test_hinzufuegen_normalisiert_und_ohne_dubletten(conn):
    assert tracking.hinzufuegen(conn, 1, "  SEO   Tool \nseo tool, website prüfen\n\n", "Marke, ratgeber") == \
        {"neu": 2, "vorhanden": 0}
    assert tracking.hinzufuegen(conn, 1, ["seo tool"], ["neu"]) == {"neu": 0, "vorhanden": 1}
    k = {x["query"]: x["tags"] for x in tracking.liste(conn, 1)}
    assert k == {"seo tool": ["marke", "neu", "ratgeber"], "website prüfen": ["marke", "ratgeber"]}
    assert [x["query"] for x in tracking.liste(conn, 1, tag="Neu")] == ["seo tool"]
    assert tracking.alle_tags(conn, 1) == [{"tag": "marke", "anzahl": 2}, {"tag": "neu", "anzahl": 1},
                                           {"tag": "ratgeber", "anzahl": 2}]


def test_tags_aendern_und_entfernen(conn):
    tracking.hinzufuegen(conn, 1, ["a", "b"], ["x"])
    tracking.tags_aendern(conn, 1, ["a", "nicht getrackt"], hinzu=["y"], weg=["x"])
    assert {x["query"]: x["tags"] for x in tracking.liste(conn, 1)} == {"a": ["y"], "b": ["x"]}
    assert tracking.entfernen(conn, 1, ["a", "gibtsnicht"]) == 1
    assert tracking.alle_tags(conn, 1) == [{"tag": "x", "anzahl": 1}]  # Tags von "a" mit gelöscht
    with pytest.raises(tracking.TrackingFehler):
        tracking.hinzufuegen(conn, 1, " \n ")
    with pytest.raises(tracking.TrackingFehler):
        tracking.hinzufuegen(conn, 1, "x" * 201)


def test_nur_getrackte_begriffe_zaehlen(conn):
    laden(conn, [zeile("2026-10-01", "a", position=1), zeile("2026-10-01", "b", position=50),
                 zeile("2026-10-01", "c", position=12, impressionen=10)])
    # leere Liste: alle zählen
    u = positionen.uebersicht(conn, 1, tage=1)
    assert u["auswahl"] == "alle" and u["kennzahlen"]["gezaehlt"] == 3
    # Liste mit a und einem Begriff ohne Daten → Sichtbarkeit (100 + 0) / 2
    tracking.hinzufuegen(conn, 1, ["a", "ohne daten"], ["marke"])
    tracking.hinzufuegen(conn, 1, ["c"])
    u = positionen.uebersicht(conn, 1, tage=1, tag="marke")
    assert u["auswahl"] == "tracking" and u["kennzahlen"]["gezaehlt"] == 2
    assert u["kennzahlen"]["sichtbarkeit"] == 50.0 and u["kennzahlen"]["keywords"] == 1
    assert u["tage"][0]["impressionen"] == 100  # Tagesverlauf nur mit getrackten Begriffen
    kw = {x["query"]: x for x in positionen.keywords(conn, 1, 1)["keywords"]}
    assert set(kw) == {"a", "c", "ohne daten"}
    assert kw["ohne daten"]["status"] == "keine Daten" and kw["a"]["tags"] == ["marke"]
    # Ansicht "alle" zeigt trotzdem, was getrackt ist
    alle = {x["query"]: x for x in positionen.keywords(conn, 1, 1, auswahl="alle")["keywords"]}
    assert set(alle) == {"a", "b", "c"} and alle["c"]["getrackt"] and not alle["b"]["getrackt"]
    with pytest.raises(positionen.PositionenFehler):
        positionen.keywords(conn, 1, 1, auswahl="quatsch")


def test_api_und_ui_formular():
    from app.web import app
    client = TestClient(app)
    p = client.post("/api/projekte", json={"domain": "ex.de"}).json()["id"]
    client.post(f"/api/projekte/{p}/positionen/import", json={"quelle": "mock", "tage": 30, "warten": True})
    assert client.post(f"/api/projekte/{p}/tracking", json={"queries": ["seo check", "ex"], "tags": ["kern"]}
                       ).json() == {"neu": 2, "vorhanden": 0}
    u = client.get(f"/api/projekte/{p}/positionen").json()
    assert u["auswahl"] == "tracking" and u["kennzahlen"]["gezaehlt"] == 2
    assert client.post(f"/api/projekte/{p}/tracking/tags", json={"queries": ["ex"], "weg": ["kern"]}
                       ).json()["keywords"][0]["tags"] == []
    # UI: Begriffe ankreuzen und mit Tag tracken, danach Weiterleitung zurück
    r = client.post(f"/projekte/{p}/tracking", data={"aktion": "hinzufuegen", "query": ["hreflang", "llms txt"],
                                                       "tags": "technik", "zurueck": f"/projekte/{p}/positionen?tage=7"},
                    follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/projekte/{p}/positionen?tage=7"
    client.post(f"/projekte/{p}/tracking", data={"aktion": "entfernen", "query": ["ex"]})
    t = client.get(f"/api/projekte/{p}/tracking").json()
    assert [k["query"] for k in t["keywords"]] == ["hreflang", "llms txt", "seo check"]
    seite = client.get(f"/projekte/{p}/positionen?tag=technik")
    assert seite.status_code == 200 and "beobachtete (3)" in seite.text and "2 Suchbegriffe" in seite.text
    assert client.post(f"/projekte/{p}/tracking", data={"aktion": "boese"}).status_code == 400
    # fremde Weiterleitungsziele werden ignoriert
    r = client.post(f"/projekte/{p}/tracking", data={"aktion": "neu", "neu": "x", "zurueck": "https://boese.de"},
                    follow_redirects=False)
    assert r.headers["location"] == f"/projekte/{p}/positionen"
