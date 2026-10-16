"""Core Web Vitals: Formeln, Service mit Fake-Messer, eine echte Chromium-Messung auf der Testseite."""

import math
import time

import pytest
from fastapi.testclient import TestClient

from app.core import projekte, vitals
from app.crawler import vitals as messung
from app.db import verbinden


# ---------- Formeln ----------

def test_lognormal_score_wie_lighthouse():
    assert round(messung.lognormal_score(2500, 2500, 4000), 2) == 0.9   # p10 → 0,9
    assert round(messung.lognormal_score(4000, 2500, 4000), 2) == 0.5   # Median → 0,5
    assert messung.lognormal_score(0, 2500, 4000) == 1.0
    assert messung.lognormal_score(60_000, 2500, 4000) < 0.01


def test_score_und_ampel():
    gut = {"fcp": 900, "lcp": 1200, "tbt": 0, "cls": 0}
    schlecht = {"fcp": 6000, "lcp": 9000, "tbt": 2000, "cls": 0.6}
    assert messung.score(gut, "mobile") == 100 and messung.score(schlecht, "mobile") < 10
    assert messung.score({**gut, "lcp": None}, "mobile") is None
    assert messung.score({"fcp": 1600, "lcp": 2400, "tbt": 350, "cls": 0.25}, "desktop") == 50
    assert [messung.bewertung("lcp", w) for w in (2500, 2501, 4001)] == ["gut", "mittel", "schlecht"]
    assert messung.bewertung("cls", 0.1) == "gut" and messung.bewertung("cls", None) is None


# ---------- Service ----------

class FakeMesser:
    """Liefert feste Werte: Startseite schnell, alles andere langsam auf Mobil."""
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def messen(self, url, geraet):
        langsam = geraet == "mobile" and not url.endswith("/")
        m = messung.Messung(url, geraet, ttfb=100, fcp=800, lcp=5000 if langsam else 1200, cls=0.3 if langsam else 0,
                            tbt=700 if langsam else 50, bytes=100_000, anfragen=10)
        m.score = messung.score(m.als_dict(), geraet)
        return m


@pytest.fixture
def crawl(monkeypatch):
    monkeypatch.setattr(vitals, "MESSER_FABRIK", FakeMesser)
    conn = verbinden()
    p = projekte.anlegen(conn, "ex.de").id
    c = conn.execute("INSERT INTO crawls (projekt_id, start_url, status) VALUES (?, 'https://ex.de/', 'fertig')",
                     (p,)).lastrowid
    for url, rank in [("https://ex.de/", 10), ("https://ex.de/a", 90), ("https://ex.de/b", 50), ("https://ex.de/c", 5)]:
        conn.execute("INSERT INTO seiten (crawl_id, url, tiefe, status_code, woerter, link_rank) VALUES (?, ?, 1, 200, 300, ?)",
                     (c, url, rank))
    conn.execute("INSERT INTO seiten (crawl_id, url, tiefe, status_code) VALUES (?, 'https://ex.de/404', 1, 404)", (c,))
    conn.commit()
    return conn, c


def test_auswahl_startseite_dann_link_staerke(crawl):
    conn, c = crawl
    assert vitals.seiten_auswahl(conn, c, 3) == ["https://ex.de/", "https://ex.de/a", "https://ex.de/b"]


def test_messlauf_und_zusammenfassung(crawl):
    conn, c = crawl
    lauf = vitals.starten(conn, c, anzahl=2, warten=True)
    assert lauf["gesamt"] == 4
    e = vitals.ergebnis(conn, c)
    assert e["lauf"]["status"] == "fertig" and e["lauf"]["fertig"] == 4 and len(e["messungen"]) == 4
    mobil, desktop = e["zusammenfassung"]["mobile"], e["zusammenfassung"]["desktop"]
    assert mobil["bestanden"] == 1 and desktop["bestanden"] == 2
    assert mobil["lcp_median"] == (1200 + 5000) / 2
    langsam = next(m for m in e["messungen"] if m["url"].endswith("/a") and m["geraet"] == "mobile")
    assert langsam["bewertung"] == {"lcp": "schlecht", "cls": "schlecht", "tbt": "schlecht", "fcp": "gut", "ttfb": "gut"}


def test_eingaben(crawl):
    conn, c = crawl
    with pytest.raises(vitals.VitalsFehler, match="anzahl"):
        vitals.starten(conn, c, anzahl=0)
    with pytest.raises(vitals.VitalsFehler, match="Geräte"):
        vitals.starten(conn, c, geraete=("tv",))
    conn.execute("INSERT INTO vitals_laeufe (crawl_id, gesamt, lebenszeichen) VALUES (?, 1, datetime('now'))", (c,))
    conn.commit()
    with pytest.raises(vitals.VitalsFehler, match="läuft schon"):
        vitals.starten(conn, c)
    conn.execute("UPDATE vitals_laeufe SET lebenszeichen = datetime('now', '-10 minutes')")
    conn.commit()
    assert vitals.starten(conn, c, anzahl=1, warten=True)["status"] == "fertig"  # verwaister Lauf blockiert nicht


def test_ui_und_api(crawl):
    conn, c = crawl
    from app.web import app
    client = TestClient(app)
    assert "Ladezeit messen" in client.get(f"/crawls/{c}/vitals").text
    r = client.post(f"/crawls/{c}/vitals", data={"anzahl": "2"})
    assert r.status_code == 200 and 'id="vitals-status"' in r.text
    ende = time.time() + 10
    while "HX-Refresh" not in client.get(f"/crawls/{c}/vitals-status").headers:
        assert time.time() < ende
        time.sleep(0.05)
    seite = client.get(f"/crawls/{c}/vitals").text
    assert "Je Seite" in seite and "5.0 s" in seite and "Mobil" in seite
    api = client.get(f"/api/crawls/{c}/vitals").json()
    assert api["zusammenfassung"]["desktop"]["score"] == 97  # LCP 1,2 s liegt genau auf p10 (0,9)
    assert client.post(f"/api/crawls/{c}/vitals", json={"anzahl": 99}).status_code == 400


# ---------- echte Messung ----------

def test_echte_messung_auf_testseite(testseite):
    pytest.importorskip("playwright")
    try:
        with messung.Messer(drosseln=False, nachlauf_ms=300) as m:
            e = m.messen(testseite + "gut", "mobile")
    except Exception as fehler:  # Chromium nicht installiert
        pytest.skip(f"Chromium fehlt: {fehler}")
    assert e.fehler is None, e.fehler
    assert e.fcp is not None and e.ttfb is not None and e.cls == 0 and e.anfragen >= 1 and e.score is not None


# ---------- Ladezeit im Website-Zustand ----------

def test_messung_wird_zu_problemen(crawl):
    from app.core import audit, aufgaben, score
    conn, c = crawl
    audit.neu_auswerten(conn, c)
    vorher = audit._health(conn, c, "performance")
    vitals.starten(conn, c, anzahl=2, warten=True)   # misst / (schnell) und /a (mobil langsam)
    treffer = {cid: audit.issue_details(conn, c, cid)["treffer"] for cid in ("ladezeit_lcp", "ladezeit_cls", "ladezeit_tbt")}
    assert {cid: [t["url"] for t in t_] for cid, t_ in treffer.items()} == {
        "ladezeit_lcp": ["https://ex.de/a"], "ladezeit_cls": ["https://ex.de/a"], "ladezeit_tbt": ["https://ex.de/a"]}
    assert treffer["ladezeit_lcp"][0]["detail"] == "LCP 5,0 s (mobil)"
    # Anteil zählt gegen die 2 gemessenen Seiten, nicht gegen alle 4 HTML-Seiten
    assert audit._bezug(conn, c)["ladezeit_lcp"] == 2
    abzug = lambda h: -score.K * math.log(h / 100)  # noqa: E731
    neu = abzug(audit._health(conn, c, "performance")) - abzug(vorher)
    assert neu == pytest.approx(3 * score.strafe("warning", 1, False, 2), abs=0.01)
    assert audit.crawl_holen(conn, c)["health"] is not None   # gespeicherter Zustand neu berechnet
    ids = {a["id"] for a in aufgaben.liste(conn, c)["aufgaben"]}
    assert {"ladezeit_lcp", "ladezeit_cls", "ladezeit_tbt"} <= ids


def test_ohne_messung_keine_ladezeit_probleme(crawl):
    from app.core import audit
    conn, c = crawl
    audit.neu_auswerten(conn, c)
    assert not {"ladezeit_lcp", "ladezeit_cls", "ladezeit_tbt"} & set(audit._treffer_pro_check(conn, c))
    assert audit._bezug(conn, c) == {}


def test_automatisch_nach_dem_crawl(testseite, monkeypatch):
    from app.core import audit
    monkeypatch.setattr(vitals, "MESSER_FABRIK", FakeMesser)
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1").id
    assert audit.einstellungen_setzen(conn, p, start_url=testseite, crawl_delay=0, ladezeit_auto=True)["ladezeit_auto"]
    c = audit.crawl_starten(conn, p, warten=True)["id"]
    e = vitals.ergebnis(conn, c)
    assert e["lauf"]["status"] == "fertig" and e["zusammenfassung"]["mobile"]["seiten"] >= 1
    assert "ladezeit_lcp" in audit._treffer_pro_check(conn, c)   # FakeMesser: Unterseiten mobil langsam


def test_einstellung_in_der_oberflaeche():
    from app.core import audit
    from app.web import app
    conn = verbinden()
    p = projekte.anlegen(conn, "ex.de").id
    client = TestClient(app)
    assert 'name="ladezeit_auto"' in client.get(f"/projekte/{p}/einstellungen").text
    daten = {"start_url": "https://ex.de/", "seitenlimit": "50", "crawl_delay": "0.5", "user_agent": "x",
             "robots_beachten": "1", "ladezeit_auto": "1"}
    assert "Gespeichert" in client.post(f"/projekte/{p}/einstellungen", data=daten).text
    assert audit.einstellungen_holen(conn, p)["ladezeit_auto"] is True
    client.post(f"/projekte/{p}/einstellungen", data={k: v for k, v in daten.items() if k != "ladezeit_auto"})
    assert audit.einstellungen_holen(conn, p)["ladezeit_auto"] is False


def test_pdf_zeigt_ladezeit(crawl):
    from app import berichte
    conn, c = crawl
    assert "nicht gemessen" in berichte.site_audit_html(conn, c)
    vitals.starten(conn, c, anzahl=2, warten=True)
    html = berichte.site_audit_html(conn, c)
    assert "Core Web Vitals bestanden" in html and "1 von 2 Seiten" in html and "sowie die gemessene Ladezeit" in html
