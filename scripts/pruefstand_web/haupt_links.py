"""Hauptwebsite, Teil Links und Adressen: interne/externe Links, Ankertexte, URL-Form, fremde Ressourcen."""

from scripts.pruefstand_web import Website, absaetze


def _mit_links(w: Website, pfad: str, links: str, **kw) -> None:
    w.seite(pfad, inhalt=absaetze(pfad, 210) + f"<p>{links}</p>", **kw)


def intern(w: Website) -> None:
    _mit_links(w, "/nofollow-intern", '<a href="/uebersicht" rel="nofollow">Alle Testfälle</a>',
               ja=["interne_links_nofollow"])
    _mit_links(w, "/noopener-intern", '<a href="/uebersicht" rel="noopener noreferrer">Alle Testfälle</a>',
               nein=["interne_links_nofollow"])
    _mit_links(w, "/link-ohne-text", '<a href="/uebersicht"></a> <a href="/"><img src="/bilder/ok.png" alt=""></a>',
               ja=["links_ohne_anker"])
    _mit_links(w, "/link-mit-aria-label", '<a href="/uebersicht" aria-label="Alle Testfälle"><svg width="9" '
               'height="9"></svg></a>', nein=["links_ohne_anker"])
    _mit_links(w, "/bild-link-mit-alt", '<a href="/uebersicht"><img src="/bilder/ok.png" alt="Alle Testfälle"></a>',
               nein=["links_ohne_anker"])
    _mit_links(w, "/anker-hier", '<a href="/uebersicht">hier</a> <a href="/">Mehr erfahren</a>',
               ja=["nichtssagender_anker"])
    _mit_links(w, "/anker-beschreibend", '<a href="/uebersicht">hier geht es zur Übersicht aller Testfälle</a>',
               nein=["nichtssagender_anker"])
    # 2 Links im Fuß jeder Seite + 2999 bzw. 2998 im Block = 3001 bzw. 3000
    for pfad, anzahl, soll in (("/links-3001", 2999, "ja"), ("/links-3000", 2998, "nein")):
        block = '<nav>' + '<a href="/">Zurück zum Start</a> ' * anzahl + '</nav>'
        w.seite(pfad, nach_main=block, **{soll: ["zu_viele_links"]})
    _mit_links(w, "/link-syntax-kaputt", '<a href="http:/beispiel.example/seite">Partnerseite</a>',
               ja=["link_syntax_fehler"])
    _mit_links(w, "/link-syntax-tel", '<a href="tel:+49 40 1234567">Anrufen</a> '
               '<a href="mailto:info@example.org?subject=Hallo Welt">Schreiben</a>', nein=["link_syntax_fehler"])
    einzeln = {"nur_ein_eingehender_link": "nur von einer einzigen Seite verlinkt"}
    _mit_links(w, "/ein-link-quelle", '<a href="/ein-link-ziel">Einzelziel</a> <a href="/zwei-links-ziel">Doppelziel</a>')
    _mit_links(w, "/zwei-links-quelle", '<a href="/zwei-links-ziel">Doppelziel</a>')
    w.seite("/ein-link-ziel", im_menue=False, ja=["nur_ein_eingehender_link"], warum=einzeln)
    w.seite("/zwei-links-ziel", im_menue=False, nein=["nur_ein_eingehender_link"])


def adressen(w: Website) -> None:
    w.seite("/parameter?a=1&b=2&c=3&d=4&e=5", ja=["zu_viele_parameter"])
    w.seite("/parameter?a=1&b=2&c=3&d=4", nein=["zu_viele_parameter"])
    w.seite("/mit_unterstrich", ja=["unterstriche_url"])
    w.seite("/ohne-unterstrich?sortierung_neu=1", nein=["unterstriche_url"],
            warum={"unterstriche_url": "Unterstrich nur im Parameter, nicht im Pfad"})
    for laenge, soll in ((201, "ja"), (200, "nein")):
        anfang = w.url(f"/lange-adresse-{laenge}-")
        pfad = f"/lange-adresse-{laenge}-" + ("fahrrad-werkstatt-" * 20)[:laenge - len(anfang)]
        w.seite(pfad.rstrip("-") + "x" if pfad.endswith("-") else pfad, **{soll: ["url_zu_lang"]})


def extern(w: Website) -> None:
    f = w.fremd
    _mit_links(w, "/extern-defekt", f'<a href="{f}/fehlt/seite">Fremde Seite, die es nicht mehr gibt</a>',
               ja=["externe_links_defekt"])
    _mit_links(w, "/extern-ok", f'<a href="{f}/ok/seite">Fremde Seite</a> <a href="{f}/umleitung">Umgezogene Seite</a> '
               f'<a href="{f}/nur-get">Server ohne HEAD</a> <a href="{f}/ok/werbung" rel="sponsored">Anzeige</a> '
               '<a href="http://localhost:9/app">Programm öffnen</a>',
               nein=["externe_links_defekt", "externe_nofollow"],
               warum={"externe_links_defekt": "Weiterleitung auf 200, Server ohne HEAD und ein Link auf den eigenen "
                                              "Rechner (localhost) sind nicht defekt"})
    _mit_links(w, "/extern-nofollow", f'<a href="{f}/ok/partner" rel="nofollow">Partner</a>', ja=["externe_nofollow"])
    _mit_links(w, "/extern-bild-defekt", f'<img src="{f}/fehlt/bild.png" alt="Fremdes Bild">',
               ja=["externe_bilder_defekt"])
    _mit_links(w, "/extern-bild-ok", f'<img src="{f}/ok/bild.png" alt="Fremdes Bild">', nein=["externe_bilder_defekt"])
    w.seite("/extern-js-defekt", nach_main=f'<script src="{f}/fehlt/skript.js"></script>',
            ja=["externe_js_css_defekt"])
    w.seite("/extern-js-ok", nach_main=f'<script src="{f}/ok/skript.js"></script>', nein=["externe_js_css_defekt"])
    for laenge, soll in ((2001, "ja"), (2000, "nein")):
        anfang = f"{f}/ok/"
        _mit_links(w, f"/link-url-{laenge}", f'<a href="{anfang}{"a" * (laenge - len(anfang))}">Sehr lange Adresse</a>',
                   **{soll: ["link_url_zu_lang"]})


def alles(w: Website) -> None:
    intern(w)
    adressen(w)
    extern(w)
