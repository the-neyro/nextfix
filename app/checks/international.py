"""Checks: Internationales SEO (hreflang)."""

import re

from app.checks.katalog import check, json_spalte
from app.crawler.urls import normalisieren

# Sprache (ISO 639-1/-2), optional Schrift (ISO 15924), optional Region (ISO 3166 oder UN M.49)
SPRACHCODE = re.compile(r"^[a-z]{2,3}(-[a-z]{4})?(-([a-z]{2}|\d{3}))?$", re.I)


def _eintraege(conn, crawl_id):
    """(seite_id, url, [(lang, normalisierte Ziel-URL, absolut)]) für Seiten mit hreflang."""
    ergebnis = []
    for seite_id, url, liste in json_spalte(conn, crawl_id, "hreflang", "hreflang != '[]'"):
        eintraege = [(e["lang"], normalisieren(e["url"], url) or e["url"], e["absolut"]) for e in liste]
        ergebnis.append((seite_id, url, eintraege))
    return ergebnis


def _ist_gueltig(code: str) -> bool:
    return code.lower() == "x-default" or bool(SPRACHCODE.match(code))


@check("hreflang_code_ungueltig", "Ungültiger Sprachcode in hreflang", "error", "international",
       "Suchmaschinen ignorieren hreflang-Einträge, deren Sprach- oder Ländercode sie nicht kennen.",
       "Codes im Format Sprache[-Region] verwenden, z. B. de, de-AT, en-GB oder x-default.")
def hreflang_code_ungueltig(conn, crawl_id):
    treffer = []
    for seite_id, _, eintraege in _eintraege(conn, crawl_id):
        falsch = sorted({lang for lang, _, _ in eintraege if not _ist_gueltig(lang)})
        if falsch:
            treffer.append((seite_id, ", ".join(falsch)))
    return treffer


@check("hreflang_relativ", "Relative URL in hreflang", "warning", "international",
       "hreflang-Ziele sollen vollständige URLs sein, relative Angaben werden oft falsch gedeutet.",
       "Im href immer die komplette URL mit https:// und Domain angeben.")
def hreflang_relativ(conn, crawl_id):
    treffer = []
    for seite_id, _, eintraege in _eintraege(conn, crawl_id):
        relativ = [lang for lang, _, absolut in eintraege if not absolut]
        if relativ:
            treffer.append((seite_id, f"{len(relativ)} Eintrag/Einträge, z. B. {relativ[0]}"))
    return treffer


@check("hreflang_ohne_selbstbezug", "hreflang ohne Verweis auf sich selbst", "warning", "international",
       "Jede Sprachversion sollte sich in ihrer eigenen hreflang-Liste mit aufführen.",
       "Einen hreflang-Eintrag ergänzen, der auf die Seite selbst zeigt.")
def hreflang_ohne_selbstbezug(conn, crawl_id):
    return [(seite_id, None) for seite_id, url, eintraege in _eintraege(conn, crawl_id)
            if url not in {ziel for _, ziel, _ in eintraege}]


@check("hreflang_doppelt", "Sprachcode mehrfach mit verschiedenen URLs", "warning", "international",
       "Zeigt derselbe Sprachcode auf mehrere Seiten, weiß die Suchmaschine nicht, welche gemeint ist.",
       "Pro Sprachcode genau eine Ziel-URL angeben.")
def hreflang_doppelt(conn, crawl_id):
    treffer = []
    for seite_id, _, eintraege in _eintraege(conn, crawl_id):
        ziele: dict[str, set[str]] = {}
        for lang, ziel, _ in eintraege:
            ziele.setdefault(lang.lower(), set()).add(ziel)
        doppelt = sorted(lang for lang, urls in ziele.items() if len(urls) > 1)
        if doppelt:
            treffer.append((seite_id, ", ".join(doppelt)))
    return treffer


def _seiten_status(conn, crawl_id) -> dict[str, int | None]:
    return dict(conn.execute("SELECT url, status_code FROM seiten WHERE crawl_id=?", (crawl_id,)))


@check("hreflang_ziel_defekt", "hreflang zeigt auf fehlerhafte Seite", "error", "international",
       "Ein Sprachverweis auf eine Weiterleitung oder Fehlerseite wird von Suchmaschinen verworfen.",
       "Das hreflang-Ziel auf die endgültige, erreichbare URL (Status 200) setzen.")
def hreflang_ziel_defekt(conn, crawl_id):
    status = _seiten_status(conn, crawl_id)
    treffer = []
    for seite_id, _, eintraege in _eintraege(conn, crawl_id):
        defekt = [f"{ziel} ({status[ziel] or 'nicht erreichbar'})" for _, ziel, _ in eintraege
                  if ziel in status and status[ziel] != 200]
        if defekt:
            treffer.append((seite_id, "; ".join(defekt[:3])))
    return treffer


@check("hreflang_ohne_rueckverweis", "hreflang ohne Rückverweis", "error", "international",
       "hreflang gilt nur, wenn die Zielseite auch zurück verweist. Einseitige Angaben werden ignoriert.",
       "Auf der Zielseite einen hreflang-Eintrag ergänzen, der auf diese Seite zeigt.")
def hreflang_ohne_rueckverweis(conn, crawl_id):
    alle = _eintraege(conn, crawl_id)
    ziele_je_url = {url: {ziel for _, ziel, _ in eintraege} for _, url, eintraege in alle}
    treffer = []
    for seite_id, url, eintraege in alle:
        fehlend = [ziel for _, ziel, _ in eintraege
                   if ziel != url and ziel in ziele_je_url and url not in ziele_je_url[ziel]]
        if fehlend:
            treffer.append((seite_id, "; ".join(fehlend[:3])))
    return treffer


@check("hreflang_lang_konflikt", "hreflang und lang-Attribut widersprechen sich", "notice", "international",
       "Der Eintrag für die Seite selbst nennt eine andere Sprache als das lang-Attribut im HTML.",
       "Sprache im lang-Attribut und im hreflang-Selbstverweis angleichen.")
def hreflang_lang_konflikt(conn, crawl_id):
    lang_je_id = dict(conn.execute("SELECT id, lang FROM seiten WHERE crawl_id=?", (crawl_id,)))
    treffer = []
    for seite_id, url, eintraege in _eintraege(conn, crawl_id):
        html_lang = (lang_je_id.get(seite_id) or "").split("-")[0].lower()
        eigene = {lang.split("-")[0].lower() for lang, ziel, _ in eintraege
                  if ziel == url and lang.lower() != "x-default"}
        if html_lang and eigene and html_lang not in eigene:
            treffer.append((seite_id, f"lang={html_lang}, hreflang={', '.join(sorted(eigene))}"))
    return treffer
