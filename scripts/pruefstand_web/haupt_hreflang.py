"""Hauptwebsite, Teil Sprachversionen (hreflang)."""

from scripts.pruefstand_web import Website


def _seite(w: Website, pfad: str, eintraege: list[tuple[str, str]], lang: str = "de", relativ: bool = False, **kw):
    """eintraege: (Sprachcode, Pfad). Absolut, außer relativ=True."""
    links = "".join(f'<link rel="alternate" hreflang="{code}" href="{ziel if relativ else w.url(ziel)}">'
                    for code, ziel in eintraege)
    w.seite(pfad, lang=lang, kopf=links, **kw)


def alles(w: Website) -> None:
    paar = [("de", "/hl/de"), ("en", "/hl/en"), ("x-default", "/hl/de")]
    alle = ["hreflang_code_ungueltig", "hreflang_relativ", "hreflang_ohne_selbstbezug", "hreflang_doppelt",
            "hreflang_ziel_defekt", "hreflang_ohne_rueckverweis", "hreflang_lang_konflikt"]
    _seite(w, "/hl/de", paar, nein=alle)
    _seite(w, "/hl/en", paar, lang="en", nein=alle)

    _seite(w, "/hl/code-falsch", [("de", "/hl/code-falsch"), ("deutsch", "/hl/code-falsch")],
           ja=["hreflang_code_ungueltig"])
    _seite(w, "/hl/code-unterstrich", [("de", "/hl/code-unterstrich"), ("de_DE", "/hl/code-unterstrich")],
           ja=["hreflang_code_ungueltig"], warum={"hreflang_code_ungueltig": "Google: Bindestrich, kein Unterstrich"})
    _seite(w, "/hl/code-en-uk", [("de", "/hl/code-en-uk"), ("en-UK", "/hl/code-en-uk")],
           ja=["hreflang_code_ungueltig"],
           warum={"hreflang_code_ungueltig": "UK ist kein ISO-3166-Code, richtig wäre en-GB (Google-Doku)"})
    _seite(w, "/hl/code-ok", [("de", "/hl/code-ok"), ("zh-Hant-TW", "/hl/code-ok"), ("en-GB", "/hl/code-ok"),
                              ("x-default", "/hl/code-ok")], nein=["hreflang_code_ungueltig"])
    _seite(w, "/hl/code-419", [("es-419", "/hl/code-419")], lang="es", ja=["hreflang_code_ungueltig"],
           warum={"hreflang_code_ungueltig": "Google: Region nur nach ISO 3166-1 Alpha-2, 419 (UN M.49) gilt nicht"})

    _seite(w, "/hl/relativ", [("de", "/hl/relativ")], relativ=True, ja=["hreflang_relativ"])
    _seite(w, "/hl/ohne-selbst", [("en", "/hl/en")], ja=["hreflang_ohne_selbstbezug", "hreflang_ohne_rueckverweis"],
           warum={"hreflang_ohne_rueckverweis": "/hl/en verweist nicht zurück"})

    _seite(w, "/hl/doppelt", [("de", "/hl/doppelt"), ("en", "/hl/doppelt"), ("en", "/hl/doppelt-en")],
           ja=["hreflang_doppelt"])
    _seite(w, "/hl/doppelt-en", [("de", "/hl/doppelt"), ("en", "/hl/doppelt-en")], lang="en")
    _seite(w, "/hl/gleich-doppelt", [("de", "/hl/gleich-doppelt"), ("en", "/hl/gleich-doppelt"),
                                     ("EN", "/hl/gleich-doppelt")], nein=["hreflang_doppelt"],
           warum={"hreflang_doppelt": "gleiche Ziel-URL, nur Groß-/Kleinschreibung des Codes anders"})

    _seite(w, "/hl/ziel-404", [("de", "/hl/ziel-404"), ("en", "/fehlt-404")], ja=["hreflang_ziel_defekt"])
    _seite(w, "/hl/ziel-301", [("de", "/hl/ziel-301"), ("en", "/weiterleitung-301")], ja=["hreflang_ziel_defekt"])
    _seite(w, "/hl/ziel-nie-verlinkt", [("de", "/hl/ziel-nie-verlinkt"), ("en", "/hl/nie-verlinkt-404")],
           ja=["hreflang_ziel_defekt"],
           warum={"hreflang_ziel_defekt": "Ziel liefert 404, ist aber nirgends verlinkt (Crawler muss es selbst prüfen)"})

    _seite(w, "/hl/einseitig", [("de", "/hl/einseitig"), ("en", "/hl/einseitig-ziel")],
           ja=["hreflang_ohne_rueckverweis"])
    _seite(w, "/hl/einseitig-ziel", [("en", "/hl/einseitig-ziel")], lang="en")
    _seite(w, "/hl/einseitig-ohne", [("de", "/hl/einseitig-ohne"), ("en", "/hl/ohne-hreflang")],
           ja=["hreflang_ohne_rueckverweis"],
           warum={"hreflang_ohne_rueckverweis": "Zielseite hat gar kein hreflang, also auch keinen Rückverweis"})
    w.seite("/hl/ohne-hreflang", lang="en")

    _seite(w, "/hl/konflikt", [("en", "/hl/konflikt")], ja=["hreflang_lang_konflikt"])
    _seite(w, "/hl/de-at", [("de-DE", "/hl/de-at")], lang="de-AT", nein=["hreflang_lang_konflikt"])
