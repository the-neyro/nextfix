"""Checks: Title, Meta-Description, Überschriften, Text."""

from app.checks.katalog import HTML, abfrage, check
from app.checks.ki import ist_rechtsseite

TITLE_MAX = 70
TITLE_MIN = 10
META_DESC_MAX = 160   # darüber kürzt Google meist ab
META_DESC_MIN = 70    # darunter wirkt das Snippet dünn (Abgleich mit anderen Audit-Tools)
WOERTER_MIN = 200
TEXT_ANTEIL_MIN = 0.10

# Seiten mit Canonical auf eine andere URL sind gewollte Varianten, keine Duplikate
KANONISCH = "(canonical IS NULL OR canonical = url)"


def _indexierbar(tabelle: str = "") -> str:
    """noindex-Seiten (meta robots oder X-Robots-Tag) erscheinen nicht bei Google: Titel, Beschreibung,
    Überschriften und Textmenge sind dort egal. tabelle: Alias mit Punkt, z. B. "s."."""
    return (f"(COALESCE({tabelle}meta_robots, '') NOT LIKE '%noindex%' "
            f"AND COALESCE({tabelle}x_robots_tag, '') NOT LIKE '%noindex%')")


INDEXIERBAR = _indexierbar()
# Seiten, deren Suchergebnis-Darstellung zählt: erfolgreich geparst und nicht auf noindex
SUCHBAR = f"{HTML} AND {INDEXIERBAR}"


@check("title_fehlt", "Title-Tag fehlt oder ist leer", "error", "inhalt",
       "Der Seitentitel ist die blaue Überschrift im Suchergebnis und das stärkste Signal, worum es auf der Seite geht.",
       "Gib jeder Seite einen eigenen Titel, der in wenigen Wörtern sagt, worum es geht, z. B. „Fahrradreparatur in "
       "Hamburg | Radhaus Elbe“.",
       wordpress="Seite bearbeiten → im Yoast-Kasten unter dem Text „SEO-Titel“, bei Rank Math „Snippet bearbeiten“ → "
       "„Titel“. Fehlt der Titel danach immer noch, liegt es meist am Theme: Frag deinen Webbetreuer.")
def title_fehlt(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND COALESCE(title, '') = ''", crawl_id)


@check("title_doppelt", "Doppelte Title-Tags", "error", "inhalt",
       "Gleiche Titles machen es Suchmaschinen schwer, die passende Seite zu wählen.",
       "Jeden Title einzigartig formulieren.")
def title_doppelt(conn, crawl_id):
    return abfrage(conn, f"""
        SELECT s.id, s.title FROM seiten s JOIN (
            SELECT title FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND {KANONISCH} AND COALESCE(title, '') != ''
            GROUP BY title HAVING COUNT(*) > 1) d ON d.title = s.title
        WHERE s.crawl_id=? AND s.status_code=200 AND {_indexierbar('s.')} AND (s.canonical IS NULL OR s.canonical = s.url)""", crawl_id, crawl_id)


@check("meta_desc_doppelt", "Doppelte Meta-Descriptions", "warning", "inhalt",
       "Die Beschreibung zeigt Google oft unter dem Titel im Suchergebnis. Steht überall derselbe Text, erfährt "
       "niemand, warum sich gerade diese Seite lohnt.",
       "Schreib für jede Seite eine eigene Beschreibung in ein, zwei Sätzen: was auf der Seite steht und was der "
       "Leser davon hat.",
       wordpress="Seite bearbeiten → Yoast „Meta-Beschreibung“ bzw. Rank Math „Snippet bearbeiten“ → „Beschreibung“. "
       "Steht überall derselbe Text, kommt er aus einer Vorlage (Yoast: Einstellungen → Inhaltstypen, Rank Math: "
       "Titel & Meta): dort leeren und je Seite schreiben.")
def meta_desc_doppelt(conn, crawl_id):
    return abfrage(conn, f"""
        SELECT s.id, s.meta_description FROM seiten s JOIN (
            SELECT meta_description FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND {KANONISCH} AND COALESCE(meta_description, '') != ''
            GROUP BY meta_description HAVING COUNT(*) > 1) d ON d.meta_description = s.meta_description
        WHERE s.crawl_id=? AND s.status_code=200 AND {_indexierbar('s.')} AND (s.canonical IS NULL OR s.canonical = s.url)""", crawl_id, crawl_id)


@check("title_zu_lang", f"Title zu lang (> {TITLE_MAX} Zeichen)", "warning", "inhalt",
       "Lange Titles werden im Suchergebnis abgeschnitten.",
       f"Kürze den Seitentitel auf höchstens {TITLE_MAX} Zeichen, sonst schneidet Google das Ende ab. Das Wichtigste "
       "nach vorn, den Firmennamen ans Ende, Füllwörter wie „Willkommen bei“ weglassen.",
       wordpress="Yoast: Seite bearbeiten → „SEO-Titel“ (der Balken wird grün, wenn die Länge passt). Rank Math: "
       "„Snippet bearbeiten“ → „Titel“, mit Zeichenzähler.")
def title_zu_lang(conn, crawl_id):
    return abfrage(conn, f"SELECT id, length(title) || ' Zeichen' FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND length(title) > {TITLE_MAX}", crawl_id)


@check("title_zu_kurz", f"Title zu kurz (≤ {TITLE_MIN} Zeichen)", "warning", "inhalt",
       "Sehr kurze Titles sagen zu wenig über die Seite aus.",
       "Title mit Haupt-Keyword und Nutzen ergänzen.")
def title_zu_kurz(conn, crawl_id):
    return abfrage(conn, f"SELECT id, title FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND length(title) BETWEEN 1 AND {TITLE_MIN}", crawl_id)


@check("meta_desc_zu_lang", f"Meta-Description zu lang (> {META_DESC_MAX} Zeichen)", "notice", "inhalt",
       "Zu lange Beschreibungen schneidet Google im Suchergebnis ab; die Botschaft am Ende geht verloren.",
       f"Auf höchstens {META_DESC_MAX} Zeichen kürzen, das Wichtigste zuerst.")
def meta_desc_zu_lang(conn, crawl_id):
    return abfrage(conn, f"SELECT id, length(meta_description) || ' Zeichen' FROM seiten WHERE crawl_id=? AND {SUCHBAR}"
                         f" AND length(meta_description) > {META_DESC_MAX}", crawl_id)


@check("meta_desc_zu_kurz", f"Meta-Description zu kurz (< {META_DESC_MIN} Zeichen)", "notice", "inhalt",
       "Sehr kurze Beschreibungen nutzen den Platz im Suchergebnis nicht; Google ersetzt sie oft durch eigenen Text.",
       "Bau die Beschreibung auf etwa 120 bis 160 Zeichen aus: ein Satz zum Inhalt, ein Satz zum Nutzen, gern mit "
       "Ort oder Preis.",
       wordpress="Seite bearbeiten → im Yoast-Kasten unter dem Text „Meta-Beschreibung“, bei Rank Math „Snippet bearbeiten“ "
       "→ „Beschreibung“.")
def meta_desc_zu_kurz(conn, crawl_id):
    return abfrage(conn, f"SELECT id, length(meta_description) || ' Zeichen' FROM seiten WHERE crawl_id=? AND {SUCHBAR}"
                         f" AND length(meta_description) BETWEEN 1 AND {META_DESC_MIN - 1}", crawl_id)


@check("meta_desc_fehlt", "Meta-Description fehlt", "warning", "inhalt",
       "Ohne Beschreibung wählt die Suchmaschine selbst einen Textausschnitt.",
       "Schreib eine kurze Beschreibung (etwa 120 bis 160 Zeichen, also zwei Sätze): Worum geht es, und was hat der "
       "Leser davon?",
       wordpress="Seite bearbeiten → im Yoast-Kasten unter dem Text „Meta-Beschreibung“, bei Rank Math „Snippet bearbeiten“ "
       "→ „Beschreibung“.")
def meta_desc_fehlt(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND COALESCE(meta_description, '') = ''", crawl_id)


@check("h1_fehlt", "H1-Überschrift fehlt", "warning", "inhalt",
       "Die H1 zeigt Nutzern und Suchmaschinen das Thema der Seite.",
       "Eine aussagekräftige H1 pro Seite setzen.")
def h1_fehlt(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND h1_anzahl = 0", crawl_id)


@check("h1_gleich_title", "Überschrift (H1) und Seitentitel identisch", "notice", "inhalt",
       "Kein Fehler, Google stört sich nicht daran. Unterschiedliche Formulierungen können aber mehr Suchvarianten "
       "abdecken.",
       "Formuliere die Überschrift auf der Seite etwas anders als den Seitentitel.")
def h1_gleich_title(conn, crawl_id):
    # In Python vergleichen: SQLites lower() kennt nur A–Z, „Über“ und „über“ wären sonst verschieden
    zeilen = conn.execute(f"SELECT id, title, h1_text FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND h1_anzahl = 1"
                          " AND title IS NOT NULL AND h1_text IS NOT NULL", (crawl_id,))
    return [(seite_id, title) for seite_id, title, h1 in zeilen if h1.strip().casefold() == title.strip().casefold()]


@check("mehrere_h1", "Mehr als eine H1", "notice", "inhalt",
       "Für Google kein Problem, mehrere H1 sind erlaubt. Eine klare Hauptüberschrift hilft aber Lesern und "
       "Screenreadern, sich zurechtzufinden.",
       "Eine H1 behalten, weitere zu H2 machen.")
def mehrere_h1(conn, crawl_id):
    return abfrage(conn, f"SELECT id, h1_anzahl || ' × H1' FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND h1_anzahl > 1", crawl_id)


@check("wenig_text", f"Wenig Text (< {WOERTER_MIN} Wörter im Hauptinhalt)", "warning", "inhalt",
       "Faustregel, kein Google-Grenzwert: Google wertet die Länge allein nicht, es zählt, ob die Seite eine Frage "
       "wirklich beantwortet. Mit sehr wenig Text gelingt das aber selten. Gezählt wird nur der Hauptinhalt – Menü, "
       "Fußzeile und Cookie-Hinweis machen eine Seite nicht gehaltvoller. Rechtsseiten wie Impressum zählen nicht.",
       "Schreib mehr zu dem, was Besucher hier wissen wollen: Fragen von Kunden, Preise, Ablauf, Beispiele. Ist die "
       "Seite nur für den Betrieb da (Impressum, Login, Danke-Seite), sag Google, dass es sie nicht anzeigen soll "
       "(das heißt „noindex“), dann zählt sie hier nicht mehr. Zwei fast gleiche dünne Seiten kannst du auch zu "
       "einer zusammenlegen.",
       wordpress="Text: Seite bearbeiten. Für Google ausblenden: Yoast-Kasten → „Erweitert“ → „Suchmaschinen "
       "erlauben, diese Seite in den Suchergebnissen anzuzeigen?“ → „Nein“. Rank Math: „Erweitert“ → Robots-Meta → "
       "„No Index“.")
def wenig_text(conn, crawl_id):
    # Wörter im Hauptbereich (geo.woerter); ältere Crawls ohne GEO-Signale: ganze Seite. noindex zählt nicht,
    # weil die Aufgabe genau das als Lösung anbietet („… oder nimm sie aus dem Index“)
    # Rechtsseiten (Impressum, Datenschutz …) sind von Natur aus kurz und sollen gar nicht ranken
    return [(sid, f"{n} Wörter") for sid, n, url in conn.execute(f"""SELECT id, n, url FROM (
        SELECT id, url, COALESCE(json_extract(geo, '$.woerter'), woerter) AS n FROM seiten
        WHERE crawl_id=? AND {SUCHBAR})
        WHERE n < {WOERTER_MIN}""", (crawl_id,)) if not ist_rechtsseite(url)]


@check("text_html_niedrig", "Viel Code, wenig Text (≤ 10 % Text)", "notice", "inhalt",
       "Faustregel anderer SEO-Tools, für Google kein Kriterium: Weniger als 10 % der Seite ist lesbarer Text. Das "
       "kann auf dünnen Inhalt oder viel überflüssigen Code hinweisen.",
       "Ergänze Text. Bleibt der Wert niedrig, lass prüfen, welche eingebetteten Skripte und Styles überflüssig sind.")
def text_html_niedrig(conn, crawl_id):
    return abfrage(conn, f"SELECT id, round(text_anteil * 100, 1) || ' %' FROM seiten WHERE crawl_id=? AND {SUCHBAR} AND text_anteil <= {TEXT_ANTEIL_MIN}", crawl_id)


@check("bilder_ohne_alt", "Bilder ohne alt-Attribut", "warning", "inhalt",
       "Der Alternativtext beschreibt ein Bild in Worten: Screenreader lesen ihn blinden Menschen vor, und Google "
       "versteht damit, was das Bild zeigt.",
       "Beschreib jedes Bild, das etwas zeigt, in ein paar Wörtern, z. B. „Mechaniker stellt die Bremse am E-Bike "
       "ein“. Reine Schmuckbilder (Linien, Hintergründe) lässt du leer.",
       wordpress="Im Editor: Bild anklicken → rechts „Alternativer Text“. Das Feld in der Mediathek gilt nur für Bilder, "
       "die du danach neu einfügst, schon eingebaute Bilder änderst du im Editor.")
def bilder_ohne_alt(conn, crawl_id):
    return abfrage(conn, """
        SELECT seite_id, COUNT(*) || ' Bild(er)' FROM links
        WHERE crawl_id=? AND art='img' AND alt IS NULL GROUP BY seite_id""", crawl_id)
