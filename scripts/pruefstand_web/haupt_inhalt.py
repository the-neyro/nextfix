"""Hauptwebsite, Teil Inhalt: Titel, Beschreibung, Überschriften, Textmenge, Duplikate, strukturierte Daten."""

import re

from scripts.pruefstand_web import Website, absaetze, auf_laenge

DESC_FUELLER = " Reparatur, Inspektion und Beratung rund ums Fahrrad am Elbufer, schnell und ehrlich erklärt"


def titel(w: Website) -> None:
    w.seite("/ohne-title", titel=False, ja=["title_fehlt"])
    w.seite("/title-leer", titel="", ja=["title_fehlt"], nein=["title_zu_kurz"])
    w.seite("/noindex-ohne-title", titel=False, noindex=True, nein=["title_fehlt"])
    w.seite("/title-71", titel=auf_laenge("Titeltest 71: ", 71), ja=["title_zu_lang"])
    w.seite("/title-70", titel=auf_laenge("Titeltest 70: ", 70), nein=["title_zu_lang"])
    w.seite("/title-70-umlaute", titel=auf_laenge("Größenprüfung für Überschriften: Fahrräder, Öl und Bügel ", 70),
            nein=["title_zu_lang"], warum={"title_zu_lang": "70 Zeichen mit Umlauten (Zeichen, nicht Bytes zählen)"})
    # DataForSEO meldet schon ab etwa 65 Zeichen, Google nennt keine feste Grenze (Kürzung nach Pixelbreite)
    w.seite("/title-66", titel=auf_laenge("Titeltest 66: ", 66), nein=["title_zu_lang"])
    w.seite("/title-68", titel=auf_laenge("Titeltest 68: ", 68), nein=["title_zu_lang"])
    w.seite("/title-10", titel="Titel Nr10", ja=["title_zu_kurz"])
    w.seite("/title-11", titel="Titel Nr 11", nein=["title_zu_kurz", "title_fehlt"])
    # gleiche Titel: Variante mit Canonical und noindex-Seite zählen nicht
    gleich = "Gleicher Titel auf zwei Seiten im Prüfstand"
    w.seite("/doppelt-title-a", titel=gleich, ja=["title_doppelt"])
    w.seite("/doppelt-title-b", titel=gleich, ja=["title_doppelt"])
    w.seite("/doppelt-title-variante", titel=gleich, canonical="/doppelt-title-a", nein=["title_doppelt"])
    w.seite("/doppelt-title-noindex", titel=gleich, noindex=True, nein=["title_doppelt"])


def beschreibung(w: Website) -> None:
    w.seite("/ohne-desc", beschreibung=False, ja=["meta_desc_fehlt"])
    w.seite("/desc-leer", beschreibung="", ja=["meta_desc_fehlt"], nein=["meta_desc_zu_kurz"])
    w.seite("/noindex-ohne-desc", beschreibung=False, noindex=True, nein=["meta_desc_fehlt"])
    w.seite("/desc-161", beschreibung=auf_laenge("Beschreibungstest 161:", 161, DESC_FUELLER), ja=["meta_desc_zu_lang"])
    w.seite("/desc-160", beschreibung=auf_laenge("Beschreibungstest 160:", 160, DESC_FUELLER),
            nein=["meta_desc_zu_lang"])
    w.seite("/desc-69", beschreibung=auf_laenge("Beschreibungstest 69:", 69, DESC_FUELLER), ja=["meta_desc_zu_kurz"])
    w.seite("/desc-70", beschreibung=auf_laenge("Beschreibungstest 70:", 70, DESC_FUELLER),
            nein=["meta_desc_zu_kurz", "meta_desc_fehlt"])
    gleich = "Diese Beschreibung steht auf zwei Seiten des Prüfstands und ist deshalb doppelt, sonst passt alles."
    w.seite("/doppelt-desc-a", beschreibung=gleich, ja=["meta_desc_doppelt"])
    w.seite("/doppelt-desc-b", beschreibung=gleich, ja=["meta_desc_doppelt"])
    w.seite("/doppelt-desc-variante", beschreibung=gleich, canonical="/doppelt-desc-a", nein=["meta_desc_doppelt"])
    w.seite("/doppelt-desc-noindex", beschreibung=gleich, noindex=True, nein=["meta_desc_doppelt"])


def ueberschriften(w: Website) -> None:
    w.seite("/ohne-h1", h1=False, inhalt=absaetze("ohne-h1", 220), ja=["h1_fehlt"])
    w.seite("/h1-nur-bild", h1=False, inhalt='<h1><img width="40" height="40" src="/bilder/ok.png" alt="Radhaus Logo"></h1>'
            + absaetze("h1-nur-bild", 220), nein=["h1_fehlt"])
    t = "Gleich lautender Titel und Überschrift im Test"
    w.seite("/h1-gleich-title", titel=t, h1=t.lower(), ja=["h1_gleich_title"])
    w.seite("/h1-fast-gleich", titel="Fast gleicher Titel und Überschrift im Test", h1="Fast gleiche Überschrift im Test",
            nein=["h1_gleich_title"])
    w.seite("/zwei-h1", inhalt="<h1>Zweite Hauptüberschrift</h1>" + absaetze("zwei-h1", 216), ja=["mehrere_h1"])
    w.seite("/h1-und-h2", inhalt="<h2>Unterüberschrift</h2>" + absaetze("h1-und-h2", 217), nein=["mehrere_h1"])


def textmenge(w: Website) -> None:
    w.seite("/woerter-199", woerter_main=199, ja=["wenig_text"])
    w.seite("/woerter-200", woerter_main=200, nein=["wenig_text"])
    # Übersicht aus Karten: wenig Fließtext, aber über 200 Wörter (DataForSEO: low_character_count)
    karten = "".join(f'<article><h2><a href="/uebersicht">Leistung {i}</a></h2>{absaetze(f"karte-{i}", 16)}</article>'
                     for i in range(1, 13))
    w.seite("/karten-uebersicht", inhalt=karten, nein=["wenig_text"],
            warum={"wenig_text": "Google kennt keine Mindestwortzahl, Übersichtsseiten sind legitim"})
    w.seite("/noindex-duenn", woerter_main=40, noindex=True, nein=["wenig_text"])
    # Text-Anteil: Text / HTML. Padding als CSS im <head> (zählt zum HTML, nicht zum Text)
    for pfad, ziel, soll in (("/text-anteil-8", 0.08, "ja"), ("/text-anteil-12", 0.12, "nein")):
        inhalt = absaetze(pfad, 218)
        probe = len(w.seite(pfad, inhalt=inhalt, im_menue=False))   # Länge ohne Polster, wird gleich ersetzt
        w._nr -= 1
        polster = max(0, int(sichtbarer_text(inhalt) / ziel) - probe - 20)
        w.seite(pfad, inhalt=inhalt, kopf=f"<style>/*{'x' * polster}*/</style>", **{soll: ["text_html_niedrig"]})
    w.seite("/bild-ohne-alt", inhalt=absaetze("bild-ohne-alt", 218) + '<img width="40" height="40" src="/bilder/ok.png">',
            ja=["bilder_ohne_alt"])
    w.seite("/bild-alt-leer", inhalt=absaetze("bild-alt-leer", 218) + '<img width="40" height="40" src="/bilder/ok.png" alt="">',
            nein=["bilder_ohne_alt"], warum={"bilder_ohne_alt": "alt=\"\" ist richtig für Schmuckbilder"})


def duplikate(w: Website) -> None:
    text = absaetze("kopie", 218)
    w.seite("/kopie-a", inhalt=text, ja=["duplicate_content"])
    w.seite("/kopie-b", inhalt=text, ja=["duplicate_content"])
    w.seite("/kopie-canonical", inhalt=text, canonical="/kopie-a", nein=["duplicate_content", "canonical_defekt"])
    w.seite("/kopie-noindex", inhalt=text, noindex=True, nein=["duplicate_content"])
    halb = absaetze("kopie", 100) + absaetze("halb-anders", 118)
    w.seite("/halb-aehnlich", inhalt=halb, nein=["duplicate_content"])


def markup(w: Website) -> None:
    def ld(json_text: str) -> str:
        return f'<script type="application/ld+json">{json_text}</script>'
    w.seite("/markup-json-kaputt", kopf=ld('{"@context":"https://schema.org","@type":"Product","name":"Rad"'),
            ja=["markup_fehlerhaft"])
    w.seite("/markup-product-ohne-name", kopf=ld('{"@context":"https://schema.org","@type":"Product",'
            '"offers":{"@type":"Offer","price":"499","priceCurrency":"EUR"}}'), ja=["markup_fehlerhaft"])
    w.seite("/markup-product-nur-name", kopf=ld('{"@context":"https://schema.org","@type":"Product",'
            '"name":"Stadtrad Elbe"}'), ja=["markup_fehlerhaft"],
            warum={"markup_fehlerhaft": "Google: Produkt-Snippets brauchen neben name auch review, "
                                        "aggregateRating oder offers"})
    w.seite("/markup-product-ok", kopf=ld('{"@context":"https://schema.org","@type":"Product","name":"Stadtrad Elbe",'
            '"offers":{"@type":"Offer","price":"499","priceCurrency":"EUR"}}'), nein=["markup_fehlerhaft"])
    w.seite("/markup-artikel-ohne-headline", kopf=ld('{"@context":"https://schema.org","@type":"BlogPosting",'
            '"datePublished":"2026-10-01","author":{"@type":"Person","name":"Mira Beispiel"}}'),
            nein=["markup_fehlerhaft", "ki_artikel_ohne_autor_datum"],
            warum={"markup_fehlerhaft": "Google: Article hat keine Pflichtfelder (headline ist nur empfohlen)"})


def alles(w: Website) -> None:
    titel(w)
    beschreibung(w)
    ueberschriften(w)
    textmenge(w)
    duplikate(w)
    markup(w)



def sichtbarer_text(html_text: str) -> int:
    """Zeichen des sichtbaren Hauptinhalts plus Fußzeile (wie Nextfix: Leerraum zusammengefasst)."""
    fuss = "Startseite des Prüfstands · Alle Testfälle im Überblick"
    return len(" ".join(re.sub(r"<[^>]+>", " ", html_text).split())) + len(fuss) + 15
