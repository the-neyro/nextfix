"""Hauptwebsite, Teil Crawlbarkeit: Statuscodes, Weiterleitungen, Sperren, Klicktiefe, JS-Apps."""

from scripts.pruefstand_web import Website, absaetze

GOOGLE_NONE = "Google: robots „none“ bedeutet noindex, nofollow"
GOOGLE_BOT = "Google beachtet auch <meta name=\"googlebot\">"


def statuscodes(w: Website) -> None:
    w.status("/fehlt-404", 404, ja=["status_4xx"], nein=["status_5xx"])
    w.status("/fehlt-410", 410, ja=["status_4xx"])
    w.status("/serverfehler-500", 500, ja=["status_5xx"], nein=["status_4xx"])
    w.status("/serverfehler-503", 503, ja=["status_5xx"])
    w.status("/abbruch", 200, abbrechen=True, ja=["nicht_erreichbar"])
    w.seite("/links-defekt", inhalt=absaetze("links-defekt", 200) + (
        '<p><a href="/fehlt-404">Alte Preisliste</a> <a href="/fehlt-410">Altes Angebot</a> '
        '<a href="/serverfehler-500">Terminbuchung</a> <a href="/serverfehler-503">Werkstattkalender</a> '
        '<a href="/abbruch">Gutscheine</a></p>'), ja=["interne_links_defekt"])
    w.seite("/links-gesperrt", inhalt=absaetze("links-gesperrt", 210) + (
        '<p><a href="/gesperrt/seite">Interner Bereich</a></p>'), nein=["interne_links_defekt"])

    w.seite("/langsam-0-5", verzoegerung=0.5, nein=["langsame_seite"])
    w.seite("/langsam-1-5", verzoegerung=1.5, nein=["langsame_seite", "nicht_erreichbar"],
            warum={"langsame_seite": "Grenze 1,8 s (web.dev: Server-Antwort ab 1,8 s schlecht)"})
    w.seite("/langsam-2-2", verzoegerung=2.2, ja=["langsame_seite"], nein=["nicht_erreichbar"])
    w.seite("/sehr-langsam", verzoegerung=5.5, ja=["nicht_erreichbar"], nein=["langsame_seite"],
            warum={"langsame_seite": "über 5 s zählt als „lädt nicht“, nicht doppelt als langsam"})


def weiterleitungen(w: Website) -> None:
    links = ""
    for code in (301, 302, 307, 308):
        links += f'<a href="/weiterleitung-{code}">Umzug {code}</a> '
    links += ('<a href="/kette4-1">Lange Kette</a> <a href="/kette3-1">Kurze Kette</a> '
              '<a href="/schleife-a">Schleife</a>')
    w.seite("/weiterleitungen", inhalt=absaetze("weiterleitungen", 200) + f"<p>{links}</p>",
            nein=["interne_links_defekt"])
    w.weiterleitung("/weiterleitung-301", "/", 301, ja=["perm_redirect"], nein=["temp_redirect"])
    w.weiterleitung("/weiterleitung-308", "/uebersicht", 308, ja=["perm_redirect"], nein=["temp_redirect"])
    w.weiterleitung("/weiterleitung-302", "/", 302, ja=["temp_redirect"], nein=["perm_redirect"])
    w.weiterleitung("/weiterleitung-307", "/uebersicht", 307, ja=["temp_redirect"])

    nur_umweg = {"perm_redirect": "Auf diese Adresse zeigt kein interner Link, nur eine andere Weiterleitung "
                                  "(steckt schon in „Redirect-Ketten“)"}
    # 4 Weiterleitungen hintereinander: mehr als 3 = Kette
    w.weiterleitung("/kette4-1", "/kette4-2", ja=["redirect_kette", "perm_redirect"])
    w.weiterleitung("/kette4-2", "/kette4-3", nein=["redirect_kette", "perm_redirect"], warum=nur_umweg)
    w.weiterleitung("/kette4-3", "/kette4-4", nein=["perm_redirect"], warum=nur_umweg)
    w.weiterleitung("/kette4-4", "/", nein=["perm_redirect"], warum=nur_umweg)
    # genau 3: noch erlaubt
    w.weiterleitung("/kette3-1", "/kette3-2", ja=["perm_redirect"], nein=["redirect_kette"])
    w.weiterleitung("/kette3-2", "/kette3-3", nein=["perm_redirect"], warum=nur_umweg)
    w.weiterleitung("/kette3-3", "/", nein=["perm_redirect"], warum=nur_umweg)
    w.weiterleitung("/schleife-a", "/schleife-b", ja=["redirect_kette", "perm_redirect"])
    w.weiterleitung("/schleife-b", "/schleife-a", ja=["redirect_kette"], nein=["perm_redirect"], warum=nur_umweg)


def sperren(w: Website) -> None:
    # robots.txt sperrt /gesperrt/ (siehe haupt.py); Seite wird verlinkt, aber nie abgerufen
    w.status("/gesperrt/seite", 200, ja=["blockiert"])
    w.seite("/noindex-meta", noindex=True)
    w.seite("/robots-none", robots="none", ja=["blockiert"], warum={"blockiert": GOOGLE_NONE})
    w.seite("/googlebot-noindex", kopf='<meta name="googlebot" content="noindex">', ja=["blockiert"],
            warum={"blockiert": GOOGLE_BOT})
    w.seite("/noimageindex", robots="noimageindex", nein=["blockiert"],
            warum={"blockiert": "noimageindex sperrt nur Bilder, nicht die Seite"})
    w.seite("/index-follow", robots="index, follow", nein=["blockiert"])
    w.seite("/x-robots-noindex", header={"X-Robots-Tag": "noindex"}, ja=["x_robots_noindex"], nein=["blockiert"],
            warum={"blockiert": "X-Robots-Tag hat eine eigene Prüfung, nicht doppelt melden"})
    w.seite("/x-robots-noarchive", header={"X-Robots-Tag": "noarchive"}, nein=["x_robots_noindex"])


def tiefe(w: Website) -> None:
    einzeln = {"nur_ein_eingehender_link": "nur von der vorigen Seite der Kette verlinkt"}
    w.seite("/tief-1", inhalt=absaetze("tief-1", 210) + '<p><a href="/tief-2">Zweite Ebene</a></p>')
    w.seite("/tief-2", inhalt=absaetze("tief-2", 210) + '<p><a href="/tief-3">Dritte Ebene</a></p>',
            im_menue=False, ja=["nur_ein_eingehender_link"], warum=einzeln)
    w.seite("/tief-3", inhalt=absaetze("tief-3", 210) + '<p><a href="/tief-4">Vierte Ebene</a></p>',
            im_menue=False, ja=["nur_ein_eingehender_link"], nein=["klicktiefe"], warum=einzeln)
    w.seite("/tief-4", im_menue=False, ja=["klicktiefe", "nur_ein_eingehender_link"], warum=einzeln)


def js_apps(w: Website) -> None:
    w.datei("/js/app.js", "window.app=1;", "application/javascript")
    container = '<div id="root"></div>'
    skript = '<script src="/js/app.js" defer></script>'
    w.seite("/js-app-leer", inhalt=container, nach_main=skript,
            ja=["js_app_ohne_rendern", "wenig_text"],
            warum={"wenig_text": "ohne JavaScript stehen nur 2 Wörter im Hauptinhalt"})
    w.seite("/js-app-mit-text", inhalt=absaetze("js-app-mit-text", 218) + container, nach_main=skript,
            nein=["js_app_ohne_rendern"], warum={"js_app_ohne_rendern": "Text steht schon im HTML"})


def alles(w: Website) -> None:
    statuscodes(w)
    weiterleitungen(w)
    sperren(w)
    tiefe(w)
    js_apps(w)
