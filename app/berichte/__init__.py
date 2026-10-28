"""PDF-Berichte: HTML-Vorlage (Jinja) → PDF über headless Chromium (Playwright).

Einmalig nötig: .venv/bin/playwright install chromium
"""

import base64
import sqlite3
from datetime import date, datetime, timezone
from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import checks
from app.core import audit, aufgaben, projekte, themen, vergleich, vitals

VORLAGEN = Environment(loader=FileSystemLoader(Path(__file__).with_name("vorlagen")), autoescape=select_autoescape())

FUSSZEILE = """<div style="font: 7.5px -apple-system, 'Helvetica Neue', Arial, sans-serif; color:#5f6672; width:100%; padding:0 18mm; display:flex; justify-content:space-between">
  <span>{titel}</span><span>Seite <span class="pageNumber"></span> von <span class="totalPages"></span></span></div>"""

MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember")
BEISPIELE_JE_PROBLEM = 3
MASSNAHMEN_MAX = 10
SCHRIFTEN = Path(__file__).parent.parent / "web" / "static" / "fonts"
SCHRIFT_DATEI = "dm-sans-latin-var"  # variabel, Gewichte 400 bis 700; Umlaute und ß liegen im Latin-Teil


@cache
def schriften_css() -> str:
    """@font-face mit eingebetteten Dateien – die PDF-Seite hat keine URL, von der sie laden könnte."""
    pfad = SCHRIFTEN / f"{SCHRIFT_DATEI}.woff2"
    if not pfad.exists():
        return ""
    daten = base64.b64encode(pfad.read_bytes()).decode()
    return (f'@font-face {{ font-family: "DM Sans"; font-weight: 400 700; font-style: normal; '
            f'src: url(data:font/woff2;base64,{daten}) format("woff2"); }}')


def _ortszeit(wert: str | None) -> str:
    if not wert:
        return "–"
    t = datetime.fromisoformat(str(wert)).replace(tzinfo=timezone.utc).astimezone()
    return t.strftime("%d.%m.%Y, %H:%M Uhr")


def _datum(d: date) -> str:
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def site_audit_daten(conn: sqlite3.Connection, crawl_id: int) -> dict:
    ue = audit.uebersicht(conn, crawl_id)
    try:
        v = vergleich.vergleich(conn, crawl_id)
    except audit.AuditFehler:
        v = None
    a = aufgaben.liste(conn, crawl_id)
    for i in a["aufgaben"][:MASSNAHMEN_MAX]:
        treffer = audit.issue_details(conn, crawl_id, i["id"], limit=BEISPIELE_JE_PROBLEM)["treffer"]
        i["beispiele"] = [t["url"] for t in treffer if t["url"] and not t["ausgeblendet"]]
    return {
        "aufg": a, "massnahmen_max": MASSNAHMEN_MAX, "schriften": schriften_css(),
        "abgeschlossen": _ortszeit(ue["crawl"]["beendet_am"] or ue["crawl"]["gestartet_am"]),
        "projekt": projekte.holen(conn, ue["crawl"]["projekt_id"]),
        "ue": ue,
        "themen": [themen.thema(conn, crawl_id, k) for k in checks.KATEGORIEN],
        "vergleich": v,
        "ladezeit": vitals.ergebnis(conn, crawl_id)["zusammenfassung"],
        "datum": _datum(date.today()),
    }


def site_audit_html(conn: sqlite3.Connection, crawl_id: int) -> str:
    return VORLAGEN.get_template("site_audit.html").render(**site_audit_daten(conn, crawl_id))


def html_zu_pdf(html: str, fusszeile: str = "") -> bytes:
    """Nicht im laufenden asyncio-Loop aufrufen (MCP: per asyncio.to_thread)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            seite = browser.new_page()
            seite.set_content(html, wait_until="load")
            return seite.pdf(format="A4", print_background=True, display_header_footer=True,
                             header_template="<span></span>", footer_template=FUSSZEILE.format(titel=fusszeile),
                             margin={"top": "16mm", "bottom": "18mm", "left": "18mm", "right": "18mm"})
        finally:
            browser.close()


def site_audit_pdf(conn: sqlite3.Connection, crawl_id: int) -> bytes:
    daten = site_audit_daten(conn, crawl_id)
    html = VORLAGEN.get_template("site_audit.html").render(**daten)
    return html_zu_pdf(html, f"Prüfbericht {daten['projekt'].domain}, {daten['datum']}")
