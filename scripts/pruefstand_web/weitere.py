"""Weitere Test-Websites: Fälle, die nur einmal pro Website auftreten (robots.txt, Sitemap, llms.txt …),
brauchen eigene Websites für „muss anschlagen“ und „darf nicht anschlagen“.
JS und Tempo brauchen Chromium (JavaScript ausführen, Ladezeit messen)."""

import html

from scripts.pruefstand_web import ORGANISATION, Website, absaetze, grundausstattung, png, sitemap

BOM = "﻿"
KLEIN = {"nur_ein_eingehender_link": "kleine Website: die Übersicht verlinkt nur die Startseite"}
SITE_WEIT = ["robots_fehlt", "robots_formatfehler", "robots_unbekannte_felder", "sitemap_fehlt", "sitemap_nicht_in_robots", "sitemap_formatfehler",
             "llms_fehlt", "llms_format", "llms_duenn", "llms_tote_links", "ki_bots_blockiert",
             "ki_training_bots_blockiert", "ohne_last_modified", "sitemap_zu_gross"]


def sauber(w: Website) -> Website:
    """Alles richtig, mit zwei Stolpersteinen aus der Praxis: BOM am Anfang von robots.txt und llms.txt
    (Windows-Editoren) und ein KI-Bot, der nur einen Unterordner nicht darf."""
    w.seite("/leistungen")
    w.seite("/kontakt")
    w.seite("/intern/notizen", ja=["blockiert"],
            warum={"blockiert": "robots.txt sperrt /intern/ (Datei beginnt mit BOM, Google ignoriert den BOM)"})
    graph = ('<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebSite",'
             '"name":"Prüfstand sauber","url":"/"},{"@type":"LocalBusiness","name":"Radhaus Prüfstand (erfunden)",'
             '"address":{"@type":"PostalAddress","streetAddress":"Musterstraße 1","addressLocality":"Hamburg"}}]}'
             "</script>")
    w.hubs(start_kopf=graph, start_nein=["ki_ohne_entitaet"])
    w.datei("/robots.txt", f"{BOM}User-agent: *\nDisallow: /intern/\nCrawl-delay: 1\n\n"
            f"User-agent: PerplexityBot\nDisallow: /intern/\n\nSitemap: {w.basis}sitemap-index.xml\n",
            "text/plain; charset=utf-8")
    w.datei("/sitemap-index.xml", '<?xml version="1.0" encoding="UTF-8"?><sitemapindex '
            'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<sitemap><loc>{w.basis}sitemap-seiten.xml</loc></sitemap></sitemapindex>", "application/xml")
    w.datei("/sitemap-seiten.xml", sitemap(w, ["/", "/uebersicht", "/leistungen", "/kontakt"]), "application/xml")
    w.datei("/llms.txt", f"{BOM}# Prüfstand sauber\n\n> Erfundene Fahrradwerkstatt, gebaut als saubere Test-Website.\n\n"
            f"## Seiten\n- [Start]({w.basis}): Einstieg\n- [Leistungen]({w.basis}leistungen): Reparatur und Service\n"
            f"- [Kontakt]({w.basis}kontakt): Anfahrt\n", "text/plain; charset=utf-8")
    w.erwarte(nein=SITE_WEIT, warum={
        "robots_formatfehler": "BOM am Dateianfang ist erlaubt (Google ignoriert ihn)",
        "llms_format": "BOM am Dateianfang, danach korrekte H1-Zeile",
        "llms_duenn": "Kurzbeschreibung und genau 3 Links (Grenze)",
        "ki_bots_blockiert": "PerplexityBot ist nur /intern/ gesperrt, die Startseite darf er"})
    return w


def leer(w: Website) -> Website:
    """Keine robots.txt, keine Sitemap, keine llms.txt, Startseite ohne Organisations-Markup."""
    w.hubs(start_ja=["ki_ohne_entitaet"])
    w.erwarte("/uebersicht", ja=["nur_ein_eingehender_link"], warum=KLEIN)
    w.erwarte(ja=["robots_fehlt", "sitemap_fehlt", "llms_fehlt"],
              nein=["sitemap_nicht_in_robots", "robots_formatfehler", "llms_format", "ki_bots_blockiert"])
    return w


def kaputt(w: Website) -> Website:
    """robots.txt ohne Sitemap-Zeile, Sitemap mit kaputtem XML, llms.txt ohne H1."""
    w.hubs(start_kopf=ORGANISATION)
    w.erwarte("/uebersicht", ja=["nur_ein_eingehender_link"], warum=KLEIN)
    w.datei("/robots.txt", "User-agent: *\nAllow: /\n", "text/plain; charset=utf-8")
    w.datei("/sitemap.xml", f'<?xml version="1.0"?><urlset><url><loc>{w.basis}</loc></url>', "application/xml")
    w.datei("/llms.txt", f"Prüfstand kaputt\n\n- [Start]({w.basis})\n", "text/plain; charset=utf-8")
    w.erwarte(ja=["sitemap_nicht_in_robots", "sitemap_formatfehler", "llms_format"],
              nein=["sitemap_fehlt", "robots_fehlt", "llms_fehlt", "llms_duenn"],
              warum={"sitemap_fehlt": "sitemap.xml ist da, nur kaputt"})
    return w


def riesig(w: Website) -> Website:
    """Sitemap-Index mit einer Datei über der Grenze (50.001 URLs) und einer genau auf der Grenze (50.000)."""
    w.hubs(start_kopf=ORGANISATION, start_ja=["sitemap_falsche_seiten"],
           warum={"sitemap_falsche_seiten": "die Startseite steht 100.001-mal in den Sitemaps"})
    w.erwarte("/uebersicht", ja=["nur_ein_eingehender_link"], warum=KLEIN)
    grundausstattung(w)
    w.datei("/robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {w.basis}sitemap-index.xml\n", "text/plain; charset=utf-8")
    w.datei("/sitemap-index.xml", '<?xml version="1.0" encoding="UTF-8"?><sitemapindex '
            'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<sitemap><loc>{w.basis}sitemap-50001.xml</loc></sitemap>"
            f"<sitemap><loc>{w.basis}sitemap-50000.xml</loc></sitemap></sitemapindex>", "application/xml")
    eintrag = f"<url><loc>{html.escape(w.basis)}</loc></url>"
    for anzahl in (50_001, 50_000):
        w.datei(f"/sitemap-{anzahl}.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset '
                f'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{eintrag * anzahl}</urlset>', "application/xml")
    w.erwarte(ja=[("sitemap_zu_gross", "sitemap-50001.xml")], nein=[("sitemap_zu_gross", "sitemap-50000.xml")])
    return w


def js(w: Website) -> Website:
    """Gecrawlt MIT „JavaScript ausführen“."""
    def skript(text: str, ziel: str) -> str:
        return f"<script>document.getElementById('{ziel}').insertAdjacentHTML('beforeend', {text!r});</script>"
    w.seite("/nur-js", inhalt='<div id="app"></div>', nach_main=skript(absaetze("nur-js", 250), "app"),
            ja=["inhalt_nur_per_js"], nein=["js_rendern_fehlgeschlagen"],
            warum={"js_rendern_fehlgeschlagen": "Chromium lädt die Seite normal"})
    w.seite("/teils-js", inhalt=absaetze("teils-js", 218) + '<div id="mehr"></div>',
            nach_main=skript(absaetze("teils-js-mehr", 40), "mehr"), nein=["inhalt_nur_per_js"])
    w.seite("/js-leer-bleibt", inhalt='<div id="root"></div>', nach_main="<script>window.x = 1;</script>",
            ja=["wenig_text"], nein=["js_app_ohne_rendern"],
            warum={"js_app_ohne_rendern": "mit JavaScript geprüft, der Hinweis ist dann überflüssig",
                   "wenig_text": "auch mit JavaScript nur 2 Wörter"})
    w.seite("/js-rendern-scheitert", inhalt='<div id="root"></div>', nach_main="<script>window.x = 1;</script>",
            nur_erster_get=True, ja=[("js_rendern_fehlgeschlagen", "ERR_EMPTY_RESPONSE")], nein=["wenig_text", "js_app_ohne_rendern"],
            warum={"js_rendern_fehlgeschlagen": "Chromium bekommt beim zweiten Abruf keine Antwort",
                   "wenig_text": "Rendern gescheitert: Inhalt unbekannt, kein Fehlalarm aus dem leeren HTML"})
    w.hubs(start_kopf=ORGANISATION)
    grundausstattung(w)
    return w


def tempo(w: Website) -> Website:
    """Ladezeit (mobil, gedrosselt wie Lighthouse): ein langsames Hauptbild, springendes Layout, träges Skript."""
    w.datei("/bilder/gross-langsam.png", png(400, 300, rauschen=True), "image/png", verzoegerung=3.0)

    def kurz(saat: str) -> str:
        return absaetze(saat, 200, absatz=25)
    w.seite("/lcp-langsam", inhalt='<img src="/bilder/gross-langsam.png" alt="Werkstatt von innen" width="400" '
            'height="300" style="width:100%;height:auto">' + kurz("lcp"), ja=["ladezeit_lcp"], nein=["ladezeit_cls"])
    w.seite("/cls-springt", inhalt=kurz("cls"), ja=["ladezeit_cls"], nein=["ladezeit_lcp"], nach_main=(
        "<script>addEventListener('load', () => setTimeout(() => { const d = document.createElement('div');"
        " d.style.height = '600px'; document.querySelector('main').prepend(d); }, 300));</script>"))
    w.seite("/tbt-traege", inhalt=kurz("tbt"), ja=["ladezeit_tbt"], nach_main=(
        "<script>addEventListener('load', () => setTimeout(() => { const t = Date.now();"
        " while (Date.now() - t < 2000) {} }, 300));</script>"))
    w.hubs(start_kopf=ORGANISATION, start_nein=["ladezeit_lcp", "ladezeit_cls", "ladezeit_tbt"])
    grundausstattung(w)
    return w
