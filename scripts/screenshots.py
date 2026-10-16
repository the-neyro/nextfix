"""Screenshots für die README: baut eine eigene Demo-Datenbank (data/demo.db) mit der erfundenen Website
„Radhaus Elbe“ (scripts/demo_website.py) und fotografiert die Web-UI hell und dunkel.

Die echte Datenbank (data/seo.db) bleibt unberührt, es gehen keine Anfragen an fremde Websites.
Start: .venv/bin/python -m scripts.screenshots   → Bilder in docs/screenshots/
"""

import os
import sys
import threading
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DEMO_DB = WURZEL / "data" / "demo.db"
ZIEL = WURZEL / "docs" / "screenshots"
PORT_APP = 8011

# Vor allen app-Importen: eigene Datenbank
os.environ["SEO_DB"] = str(DEMO_DB)
for datei in DEMO_DB.parent.glob(DEMO_DB.name + "*"):   # auch -wal/-shm der letzten Demo
    datei.unlink()

from app.gsc import mock  # noqa: E402

# Testdaten passend zur Fahrradwerkstatt statt der SEO-Begriffe des Mock-Generators
mock.THEMEN = ["fahrradwerkstatt hamburg", "fahrrad reparatur altona", "e-bike service hamburg",
               "fahrrad inspektion kosten", "fahrradkette ölen", "reifendruck fahrrad", "lastenrad reparatur",
               "e-bike akku test", "fahrrad leihen hamburg", "fahrrad winterfest machen", "bremsen einstellen fahrrad",
               "schlauch wechseln fahrrad", "fahrradladen altona", "e-bike inspektion kosten", "rennrad service"]
mock.DOPPELT = {"fahrradwerkstatt hamburg", "e-bike service hamburg"}

from app.core import audit, onpage, positionen, projekte, vitals  # noqa: E402
from app.db import verbinden  # noqa: E402
from scripts import demo_website  # noqa: E402


def daten_anlegen() -> int:
    _, basis = demo_website.starten()
    conn = verbinden()
    p = projekte.anlegen(conn, "radhaus-elbe.de", "Radhaus Elbe")
    # Was nur am lokalen Demo-Server liegt (kein HTTPS, kein gzip, keine Cache-Header), bleibt außen vor
    audit.einstellungen_setzen(conn, p.id, start_url=basis, crawl_delay=0, quelle="beides",
                               checks_aus=["startseite_ohne_https", "http_nicht_auf_https", "kein_hsts", "unkomprimiert",
                                           "js_css_unkomprimiert", "js_css_ohne_cache"])
    crawl = audit.crawl_starten(conn, p.id, warten=True)
    print("Prüfung fertig:", crawl["id"], "Zustand", audit._health(conn, crawl["id"]))
    positionen.importieren(conn, p.id, "mock", tage=90)
    vitals.starten(conn, crawl["id"], anzahl=5, warten=True)
    onpage.pruefen(conn, p.id, basis + "werkstatt", "fahrradwerkstatt hamburg", mit_suggest=False)
    return p.id


def app_starten() -> None:
    import uvicorn

    from app.web import app
    server = uvicorn.Server(uvicorn.Config(app, port=PORT_APP, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.1)


def fotografieren(projekt_id: int) -> None:
    from playwright.sync_api import sync_playwright

    conn = verbinden()
    crawl_id = audit.letzter_crawl_id(conn, projekt_id)
    pruefung_id = conn.execute("SELECT MAX(id) FROM onpage_pruefungen").fetchone()[0]
    basis = f"http://127.0.0.1:{PORT_APP}"
    motive = [  # (Name, Pfad, ganze Seite?)
        ("uebersicht", f"/projekte/{projekt_id}", False),
        ("problem", f"/crawls/{crawl_id}/issues/wenig_text/seite", False),
        ("seite-optimieren", f"/onpage/{pruefung_id}", False),
        ("positionen", f"/projekte/{projekt_id}/positionen", False),
        ("projekte", "/", False),
    ]
    ZIEL.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for thema in ("hell", "dunkel"):
            kontext = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2,
                                          color_scheme="light" if thema == "hell" else "dark")
            seite = kontext.new_page()
            for name, pfad, ganz in motive:
                seite.goto(basis + pfad, wait_until="networkidle")
                seite.wait_for_timeout(700)   # Zeiger der Messskala fertig animiert
                seite.screenshot(path=ZIEL / f"{name}-{thema}.png", full_page=ganz)
                print("✓", f"{name}-{thema}.png")
            kontext.close()
        mobil = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True)
        seite = mobil.new_page()
        seite.goto(f"{basis}/projekte/{projekt_id}", wait_until="networkidle")
        seite.wait_for_timeout(700)
        seite.screenshot(path=ZIEL / "mobil-hell.png")
        print("✓ mobil-hell.png")
        browser.close()


if __name__ == "__main__":
    pid = daten_anlegen()
    app_starten()
    fotografieren(pid)
    sys.exit(0)
