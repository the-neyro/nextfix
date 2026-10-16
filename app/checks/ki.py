"""Checks: Seiteninhalt für KI-Suche (Struktur, Lesbarkeit). Site-weite KI-Checks: site.py."""

import json
import re
from urllib.parse import unquote, urlsplit

from app.checks.katalog import HTML, check, json_spalte

HAUPTBEREICH = ("main", "article")


@check("ki_ohne_hauptbereich", "Kein <main> oder <article>", "notice", "ki",
       "Ohne klar markierten Hauptbereich müssen Crawler und KI-Systeme raten, welcher Text der eigentliche Inhalt ist.",
       "Den Hauptinhalt in <main> (oder <article>) fassen, Navigation und Fußzeile außerhalb lassen.")
def ki_ohne_hauptbereich(conn, crawl_id):
    return [(seite_id, None) for seite_id, _, tags in json_spalte(conn, crawl_id, "semantik")
            if not any(t in tags for t in HAUPTBEREICH)]


@check("ki_schwer_lesbar", "Inhalt schwer zu erfassen", "notice", "ki",
       "Sehr lange Absätze und Sätze oder übersprungene Überschriften-Ebenen erschweren Lesern und KI das Zusammenfassen.",
       "Absätze kürzen, Sätze teilen, Überschriften ohne Sprünge (H2 → H3) gliedern.")
def ki_schwer_lesbar(conn, crawl_id):
    return [(seite_id, "; ".join(probleme))
            for seite_id, _, probleme in json_spalte(conn, crawl_id, "lesbarkeit", "lesbarkeit != '[]'")]


# ---------- GEO: Signale aus app/crawler/geo.py (Spalte seiten.geo) ----------

MIN_WOERTER_BELEGE = 300   # erst ab hier lohnen Zahlen/Quellen
MIN_WOERTER_TEXTWAND = 600
FAQ_TYPEN = {"FAQPage", "QAPage"}
# Startseite: wer steht hinter der Website? (Typen und gängige Untertypen)
ENTITAET_TYPEN = {"Organization", "Corporation", "LocalBusiness", "Person", "ProfessionalService", "Store",
                  "NGO", "OnlineBusiness", "EducationalOrganization", "GovernmentOrganization", "MedicalOrganization"}


# Rechtstexte (AGB, Impressum, Datenschutz …) brauchen keine Zahlen oder Quellen; geprüft wird der letzte Pfadteil
RECHTSSEITE = re.compile(
    r"(.*[_-])?(agb|impressum|imprint|datenschutz\w*|privacy(-policy)?|legal|terms|nutzungsbedingungen|"
    r"widerruf\w*|cookies?(-\w+)?|disclaimer|haftungsausschluss|rechtliches)(\.\w+)?", re.I)


def ist_rechtsseite(url: str) -> bool:
    letzter = unquote(urlsplit(url).path).rstrip("/").rsplit("/", 1)[-1]
    return bool(RECHTSSEITE.fullmatch(letzter))


def _geo_seiten(conn, crawl_id, mit_url=False):
    """(seite_id, geo, markup-Typen[, url]) für HTML-Seiten mit GEO-Signalen."""
    zeilen = conn.execute(f"SELECT id, geo, markup, url FROM seiten WHERE crawl_id=? AND {HTML} AND geo IS NOT NULL",
                          (crawl_id,))
    return [(seite_id, json.loads(geo), set(json.loads(markup)["typen"]) if markup else set()) + ((url,) if mit_url else ())
            for seite_id, geo, markup, url in zeilen]


@check("ki_fragen_ohne_faq", "Fragen ohne FAQ-Markup", "notice", "ki",
       "Die Seite beantwortet mehrere Fragen (Zwischenüberschriften mit „?“), markiert sie aber nicht als FAQ. "
       "Frage-Antwort-Paare mit Markup sind für KI-Systeme leicht als Antwort zu übernehmen. "
       "Hinweis: Google zeigt FAQ-Rich-Results nur noch für Behörden- und Gesundheitsseiten.",
       "Fragen und Antworten als FAQPage (JSON-LD) auszeichnen, jede Antwort direkt unter der Frage in 1–3 Sätzen.")
def ki_fragen_ohne_faq(conn, crawl_id):
    return [(seite_id, f"{geo['fragen']} Fragen")
            for seite_id, geo, typen in _geo_seiten(conn, crawl_id)
            if geo.get("fragen", 0) >= 2 and not typen & FAQ_TYPEN]


@check("ki_ohne_belege", "Text ohne Zahlen und Quellen", "notice", "ki",
       "Längerer Text ohne konkrete Zahlen und ohne Links auf externe Quellen. Laut GEO-Studie (Princeton 2024) "
       "werden Inhalte mit Statistiken und Quellenangaben deutlich häufiger in KI-Antworten zitiert.",
       "Konkrete Zahlen (%, €, Mengen) ergänzen und Aussagen mit Links auf vertrauenswürdige Quellen belegen.")
def ki_ohne_belege(conn, crawl_id):
    return [(seite_id, f"{geo['woerter']} Wörter")
            for seite_id, geo, _, url in _geo_seiten(conn, crawl_id, mit_url=True)
            if geo.get("woerter", 0) >= MIN_WOERTER_BELEGE and not geo.get("zahlen") and not geo.get("quellen")
            and not ist_rechtsseite(url)]


@check("ki_textwand", "Langer Text ohne Gliederung", "notice", "ki",
       "Langer Text ohne Listen oder Tabellen und mit kaum Zwischenüberschriften. KI-Systeme zitieren einzelne "
       "Abschnitte – ohne Gliederung finden sie keine klar abgegrenzte Antwort.",
       "Mit H2/H3 in Abschnitte teilen, Aufzählungen und Vergleiche als Liste oder Tabelle darstellen.")
def ki_textwand(conn, crawl_id):
    return [(seite_id, f"{geo['woerter']} Wörter, {geo['zwischen']} Zwischenüberschriften")
            for seite_id, geo, _ in _geo_seiten(conn, crawl_id)
            if geo.get("woerter", 0) >= MIN_WOERTER_TEXTWAND and not geo.get("listen") and geo.get("zwischen", 0) < 2]


@check("ki_artikel_ohne_autor_datum", "Artikel ohne Autor oder Datum", "notice", "ki",
       "Bei Artikeln achten Suchmaschinen und KI-Systeme auf Aktualität und Urheber (E-E-A-T). "
       "Ohne Datum und Autor wirkt der Inhalt weniger vertrauenswürdig.",
       "datePublished/dateModified und author im Article-Markup angeben, Datum auch sichtbar mit <time datetime>.")
def ki_artikel_ohne_autor_datum(conn, crawl_id):
    treffer = []
    for seite_id, geo, _ in _geo_seiten(conn, crawl_id):
        fehlt = [name for name, schluessel in (("Datum", "datum"), ("Autor", "autor")) if not geo.get(schluessel)]
        if geo.get("artikel") and fehlt:
            treffer.append((seite_id, "fehlt: " + ", ".join(fehlt)))
    return treffer


@check("ki_ohne_entitaet", "Startseite ohne Organisations-Markup", "notice", "ki",
       "Ohne Organization- oder Person-Markup müssen KI-Systeme raten, wer hinter der Website steht. "
       "Eine klar beschriebene Marke (Name, Logo, Profile) wird eher erkannt und genannt.",
       "Auf der Startseite Organization (bzw. LocalBusiness/Person) als JSON-LD einbinden: name, url, logo, sameAs.")
def ki_ohne_entitaet(conn, crawl_id):
    # Start-URL zuerst (im Sitemap-Modus haben alle Seiten Tiefe 0), sonst die flachste Seite
    z = conn.execute(f"""SELECT s.id, s.markup FROM seiten s JOIN crawls c ON c.id = s.crawl_id
                         WHERE s.crawl_id=? AND {HTML} ORDER BY s.url = c.start_url DESC, s.tiefe, s.id LIMIT 1""",
                     (crawl_id,)).fetchone()
    if not z:
        return []
    typen = set(json.loads(z[1])["typen"]) if z[1] else set()
    return [] if typen & ENTITAET_TYPEN else [(z[0], ", ".join(sorted(typen)) or "kein Markup")]
