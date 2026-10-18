"""Prüfstand als statischer Ordner: reine Dateien mit relativen Links, z. B. für GitHub Pages, damit ein
anderes Werkzeug (z. B. DataForSEO On-Page) dieselben Fälle prüfen kann.

Was nur mit dem lokalen Server geht (Statuscodes außer 404, Weiterleitungen, eigene Header, Verzögerungen,
Seiten mit Parametern, robots.txt/Sitemap/llms.txt außerhalb der Domain-Wurzel, der „fremde“ Server),
steht in soll.json mit „nur_lokal“ und Grund. Nichts davon wird hier veröffentlicht.
"""

import json
import os
import re
from pathlib import Path

from scripts.pruefstand_web import CACHE, LETZTE_AENDERUNG, Antwort, Website

# Prüfungen, deren Ergebnis von Server-Verhalten abhängt (Header, Weiterleitungen, 5xx, Ladezeit, fremder Server)
SERVER_CHECKS = {
    "status_5xx": "Statuscode 5xx", "nicht_erreichbar": "Abbruch und Verzögerung",
    "redirect_kette": "Weiterleitungen", "temp_redirect": "Weiterleitungen", "perm_redirect": "Weiterleitungen",
    "canonical_defekt": "Ziel ist eine Weiterleitung", "hreflang_ziel_defekt": "Ziel ist eine Weiterleitung",
    "interne_links_defekt": "Ziele mit 410/5xx/Abbruch", "x_robots_noindex": "HTTP-Header",
    "langsame_seite": "Verzögerung", "unkomprimiert": "gzip steuert der Hoster", "ohne_last_modified": "HTTP-Header",
    "js_css_unkomprimiert": "gzip steuert der Hoster", "js_css_ohne_cache": "Cache-Header steuert der Hoster",
    "ohne_charset": "charset im HTTP-Header", "externe_links_defekt": "fremder Server",
    "externe_bilder_defekt": "fremder Server", "externe_js_css_defekt": "fremder Server",
    "link_url_zu_lang": "fremder Server", "ladezeit_lcp": "verzögertes Bild",
    "sitemap_falsche_seiten": "Weiterleitungen und Header in der Sitemap",
}
WURZEL_DATEIEN = ("/robots.txt", "/sitemap.xml", "/llms.txt")
SITE_GRUND = "robots.txt, Sitemap und llms.txt wirken nur an der Domain-Wurzel"
OHNE_BASIS = "ohne --export-basis werden die absoluten hreflang-Adressen relativ"


def _statisch(a: Antwort) -> bool:
    """Lässt sich die Antwort als einfache Datei nachbauen? (404 = Datei fehlt)"""
    if a.status == 404:
        return True
    if a.status != 200 or a.abbrechen or a.verzoegerung or not a.gzip:
        return False
    erlaubt = {"Last-Modified": LETZTE_AENDERUNG, **CACHE}
    return all(erlaubt.get(k) == v for k, v in a.header.items())


def _datei(pfad: str) -> str:
    """URL-Pfad → Dateipfad: /a → a/index.html, /bild.png → bild.png."""
    if pfad == "/":
        return "index.html"
    letzter = pfad.rsplit("/", 1)[-1]
    return pfad.lstrip("/") if "." in letzter else pfad.strip("/") + "/index.html"


def _relativ(text: str, w: Website, pfad: str, basis_neu: str | None) -> str:
    """Links auf die eigene Website relativ zur Datei machen (oder auf basis_neu umstellen)."""
    ordner = os.path.dirname(_datei(pfad)) or "."

    def ziel(url_pfad: str) -> str:
        if basis_neu:
            return basis_neu.rstrip("/") + url_pfad
        rel = os.path.relpath(_datei(url_pfad.split("?")[0]), ordner)
        return rel[:-len("index.html")] or "./" if rel.endswith("index.html") else rel
    text = text.replace(w.basis, "/")
    return re.sub(r'(href|src|data)="(/[^"/][^"]*|/)"', lambda m: f'{m.group(1)}="{ziel(m.group(2))}"', text)


def schreiben(websites: dict[str, Website], ordner: Path, basis_neu: str | None = None, noindex: bool = False) -> dict:
    """Schreibt alle Websites nach ordner/<name>/ plus soll.json. basis_neu: öffentliche Adresse des Ordners
    (dann absolute Links wie Canonical und hreflang); noindex: alle Seiten auf noindex (verändert viele Fälle)."""
    ordner.mkdir(parents=True, exist_ok=True)
    nur_lokal: dict[tuple[str, str], str] = {}
    for name, w in websites.items():
        for pfad, a in w.antworten.items():
            if "?" in pfad or not _statisch(a):
                nur_lokal[(name, pfad)] = "Server-Verhalten (Status, Header, Verzögerung oder Parameter)"
                continue
            if a.status == 404:
                continue
            ziel = ordner / name / _datei(pfad)
            ziel.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(a.body, bytes):
                ziel.write_bytes(a.body)
                continue
            text = _relativ(a.body, w, pfad, basis_neu and f"{basis_neu.rstrip('/')}/{name}")
            if noindex and "<head>" in text:
                text = text.replace("<head>", '<head><meta name="robots" content="noindex">', 1)
            ziel.write_text(text, encoding="utf-8")

    soll = []
    for w in websites.values():
        for s in w.soll:
            grund = (SERVER_CHECKS.get(s.check) or nur_lokal.get((s.website, s.pfad))
                     or (SITE_GRUND if s.pfad is None else None)
                     or (OHNE_BASIS if s.check.startswith("hreflang_") and not basis_neu else None))
            soll.append({"check": s.check, "website": s.website, "pfad": s.pfad, "datei": s.pfad and _datei(s.pfad),
                         "erwartet": "ja" if s.ja else "nein", "nadel": s.nadel, "warum": s.warum,
                         "nur_lokal": grund})
    (ordner / "soll.json").write_text(json.dumps(soll, ensure_ascii=False, indent=1), encoding="utf-8")
    liste = "".join(f'<li><a href="{n}/">{n}</a></li>' for n in websites)
    (ordner / "index.html").write_text(
        '<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Prüfstand Nextfix</title></head><body>'
        f"<h1>Prüfstand Nextfix</h1><p>Test-Websites mit bekannter Wahrheit, Soll: soll.json</p><ul>{liste}</ul>"
        "</body></html>", encoding="utf-8")
    return {"dateien": sum(1 for _ in ordner.rglob("*") if _.is_file()), "soll": len(soll),
            "nur_lokal": sum(1 for s in soll if s["nur_lokal"])}
