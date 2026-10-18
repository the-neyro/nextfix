"""Hauptwebsite, Teil Technik: Markup im <head>, Canonical, Größe, Kompression, defekte Dateien."""

from scripts.pruefstand_web import LANGE_WOERTER, Website, absaetze


def kopf(w: Website) -> None:
    w.seite("/ohne-viewport", viewport=None, ja=["viewport_fehlt"])
    w.seite("/viewport-ohne-width", viewport="user-scalable=yes", ja=["viewport_unvollstaendig"],
            nein=["viewport_fehlt"])
    w.seite("/viewport-nur-scale", viewport="initial-scale=1", nein=["viewport_unvollstaendig"])
    w.seite("/meta-refresh", kopf='<meta http-equiv="refresh" content="30">', ja=["meta_refresh"])
    w.seite("/ohne-lang", lang=None, ja=["ohne_lang"])
    w.seite("/lang-de-at", lang="de-AT", nein=["ohne_lang"])
    w.seite("/ohne-charset", charset=False, typ="text/html", ja=["ohne_charset"])
    w.seite("/charset-nur-header", charset=False, nein=["ohne_charset"],
            warum={"ohne_charset": "charset steht im HTTP-Header Content-Type"})
    w.seite("/charset-http-equiv", charset=False, typ="text/html",
            kopf='<meta http-equiv="Content-Type" content="text/html; charset=utf-8">', nein=["ohne_charset"])
    w.seite("/ohne-doctype", doctype="", ja=["ohne_doctype"])
    w.seite("/doctype-gross", doctype="\n<!DOCTYPE html>", nein=["ohne_doctype"])
    w.seite("/doctype-nach-kommentar", doctype="<!-- erstellt vom CMS -->\n<!doctype html>", nein=["ohne_doctype"],
            warum={"ohne_doctype": "Kommentar vor dem Doctype ist erlaubt, Browser bleiben im Standardmodus"})


def canonical(w: Website) -> None:
    w.seite("/zwei-canonicals", canonical=["/zwei-canonicals", "/uebersicht"], ja=["mehrere_canonicals"])
    w.seite("/canonical-doppelt-gleich", canonical=["/canonical-doppelt-gleich", "/canonical-doppelt-gleich"],
            nein=["mehrere_canonicals"], warum={"mehrere_canonicals": "zweimal dasselbe Ziel (Theme + Plugin) widerspricht sich nicht"})
    w.seite("/canonical-auf-404", canonical="/fehlt-404", ja=["canonical_defekt"], nein=["mehrere_canonicals"])
    w.seite("/canonical-auf-301", canonical="/weiterleitung-301", ja=["canonical_defekt"])
    w.seite("/canonical-auf-nie-verlinkt", canonical="/nie-verlinkt-404", ja=["canonical_defekt"],
            warum={"canonical_defekt": "Ziel liefert 404, ist aber nirgends verlinkt (Crawler muss es selbst prüfen)"})


def sonderfaelle(w: Website) -> None:
    leer = "Frameset-Seite hat selbst keinen Inhalt, nur Rahmen"
    w.roh("/frameset", '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" '
          'content="width=device-width, initial-scale=1"><title>Werkstatt im Rahmen: alte Frameset-Seite</title>'
          '<meta name="description" content="Eine Seite aus Rahmen wie vor zwanzig Jahren: links die Übersicht, '
          'rechts die Startseite des Prüfstands."><link rel="stylesheet" href="/stil.css"></head>'
          '<frameset cols="30%,70%"><frame src="/uebersicht"><frame src="/"></frameset></html>',
          ja=["frames", "wenig_text", "h1_fehlt", "text_html_niedrig", "ki_ohne_hauptbereich"],
          warum=dict.fromkeys(["wenig_text", "h1_fehlt", "text_html_niedrig", "ki_ohne_hauptbereich"], leer))
    w.seite("/iframe", inhalt=absaetze("iframe", 218) + '<iframe src="/uebersicht" title="Übersicht"></iframe>',
            nein=["frames"])
    w.seite("/login", inhalt=absaetze("login", 218) + '<form><input name="nutzer"><input type="Password" '
            'name="kennwort"></form>', ja=["passwort_ohne_https"])
    w.seite("/login-ohne-passwort", inhalt=absaetze("login-ohne-passwort", 218) + '<form><input name="nutzer">'
            '<input type="text" name="code"></form>', nein=["passwort_ohne_https"])
    w.seite("/flash", inhalt=absaetze("flash", 218) + '<object data="/media/film.swf" '
            'type="application/x-shockwave-flash"></object>', ja=["veraltete_plugins"])
    w.seite("/pdf-java-kurs", inhalt=absaetze("pdf-java-kurs", 218) + '<object data="/downloads/java-kurs.pdf" '
            'type="application/pdf"></object>', nein=["veraltete_plugins"],
            warum={"veraltete_plugins": "eingebettetes PDF, „java“ steht nur im Dateinamen"})
    w.seite("/video", inhalt=absaetze("video", 218) + '<embed src="/media/film.mp4" type="video/mp4">',
            nein=["veraltete_plugins"])
    w.seite("/ohne-last-modified", last_modified=False)
    w.erwarte(ja=["ohne_last_modified"])


def groesse_und_tempo(w: Website) -> None:
    for pfad, ziel, soll in (("/html-2-1mb", 2_100_000, "ja"), ("/html-1-9mb", 1_900_000, "nein")):
        punkte, n, laenge = [], 0, 0
        while laenge < ziel:
            punkte.append(f"<li>{LANGE_WOERTER[n % 8]} {LANGE_WOERTER[(n * 3 + 1) % 8]} {pfad[6:9]}{n}</li>")
            laenge += len(punkte[-1])
            n += 1
        inhalt = (absaetze(pfad, 200) + "<p>Anteil 15 %</p><h2>Alle Arbeiten</h2><ul>" + "".join(punkte) + "</ul>")
        w.seite(pfad, inhalt=inhalt, **{soll: ["html_zu_gross"]})
    w.seite("/ohne-gzip", gzip=False, ja=["unkomprimiert"])


def defekte_dateien(w: Website) -> None:
    w.seite("/bild-defekt", inhalt=absaetze("bild-defekt", 218) + '<img src="/bilder/fehlt.png" alt="Werkstatt"> ',
            ja=["interne_bilder_defekt"])
    w.seite("/bild-ok", inhalt=absaetze("bild-ok", 218) + '<img src="/bilder/ok.png" alt="Werkstatt">',
            nein=["interne_bilder_defekt"])
    w.seite("/js-defekt", nach_main='<script src="/js/fehlt.js"></script>', ja=["interne_js_css_defekt"])
    w.seite("/css-defekt", kopf='<link rel="stylesheet" href="/css/fehlt.css">', ja=["interne_js_css_defekt"])
    w.seite("/js-ok", nach_main='<script src="/js/app.js"></script>', nein=["interne_js_css_defekt"])


def alles(w: Website) -> None:
    kopf(w)
    canonical(w)
    sonderfaelle(w)
    groesse_und_tempo(w)
    defekte_dateien(w)
