"""Checks: Title, Meta-Description, Überschriften, Text."""

from app.checks.katalog import HTML, abfrage, check

TITLE_MAX = 70
TITLE_MIN = 10
META_DESC_MAX = 160   # darüber kürzt Google meist ab
META_DESC_MIN = 70    # darunter wirkt das Snippet dünn (Abgleich mit anderen Audit-Tools)
WOERTER_MIN = 200
TEXT_ANTEIL_MIN = 0.10

# Seiten mit Canonical auf eine andere URL sind gewollte Varianten, keine Duplikate
KANONISCH = "(canonical IS NULL OR canonical = url)"


@check("title_fehlt", "Title-Tag fehlt oder ist leer", "error", "inhalt",
       "Der Title ist das wichtigste On-Page-Signal und erscheint als Überschrift im Suchergebnis.",
       "Jeder Seite einen eindeutigen, beschreibenden Title geben.")
def title_fehlt(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND COALESCE(title, '') = ''", crawl_id)


@check("title_doppelt", "Doppelte Title-Tags", "error", "inhalt",
       "Gleiche Titles machen es Suchmaschinen schwer, die passende Seite zu wählen.",
       "Jeden Title einzigartig formulieren.")
def title_doppelt(conn, crawl_id):
    return abfrage(conn, f"""
        SELECT s.id, s.title FROM seiten s JOIN (
            SELECT title FROM seiten WHERE crawl_id=? AND {HTML} AND {KANONISCH} AND COALESCE(title, '') != ''
            GROUP BY title HAVING COUNT(*) > 1) d ON d.title = s.title
        WHERE s.crawl_id=? AND s.status_code=200 AND (s.canonical IS NULL OR s.canonical = s.url)""", crawl_id, crawl_id)


@check("meta_desc_doppelt", "Doppelte Meta-Descriptions", "error", "inhalt",
       "Gleiche Beschreibungen verschenken die Chance, im Suchergebnis zu überzeugen.",
       "Für jede Seite eine eigene Beschreibung schreiben.")
def meta_desc_doppelt(conn, crawl_id):
    return abfrage(conn, f"""
        SELECT s.id, s.meta_description FROM seiten s JOIN (
            SELECT meta_description FROM seiten WHERE crawl_id=? AND {HTML} AND {KANONISCH} AND COALESCE(meta_description, '') != ''
            GROUP BY meta_description HAVING COUNT(*) > 1) d ON d.meta_description = s.meta_description
        WHERE s.crawl_id=? AND s.status_code=200 AND (s.canonical IS NULL OR s.canonical = s.url)""", crawl_id, crawl_id)


@check("title_zu_lang", f"Title zu lang (> {TITLE_MAX} Zeichen)", "warning", "inhalt",
       "Lange Titles werden im Suchergebnis abgeschnitten.",
       f"Title auf höchstens {TITLE_MAX} Zeichen kürzen, Wichtiges nach vorn.")
def title_zu_lang(conn, crawl_id):
    return abfrage(conn, f"SELECT id, length(title) || ' Zeichen' FROM seiten WHERE crawl_id=? AND {HTML} AND length(title) > {TITLE_MAX}", crawl_id)


@check("title_zu_kurz", f"Title zu kurz (≤ {TITLE_MIN} Zeichen)", "warning", "inhalt",
       "Sehr kurze Titles sagen zu wenig über die Seite aus.",
       "Title mit Haupt-Keyword und Nutzen ergänzen.")
def title_zu_kurz(conn, crawl_id):
    return abfrage(conn, f"SELECT id, title FROM seiten WHERE crawl_id=? AND {HTML} AND length(title) BETWEEN 1 AND {TITLE_MIN}", crawl_id)


@check("meta_desc_zu_lang", f"Meta-Description zu lang (> {META_DESC_MAX} Zeichen)", "notice", "inhalt",
       "Zu lange Beschreibungen schneidet Google im Suchergebnis ab; die Botschaft am Ende geht verloren.",
       f"Auf höchstens {META_DESC_MAX} Zeichen kürzen, das Wichtigste zuerst.")
def meta_desc_zu_lang(conn, crawl_id):
    return abfrage(conn, f"SELECT id, length(meta_description) || ' Zeichen' FROM seiten WHERE crawl_id=? AND {HTML}"
                         f" AND length(meta_description) > {META_DESC_MAX}", crawl_id)


@check("meta_desc_zu_kurz", f"Meta-Description zu kurz (< {META_DESC_MIN} Zeichen)", "notice", "inhalt",
       "Sehr kurze Beschreibungen nutzen den Platz im Suchergebnis nicht; Google ersetzt sie oft durch eigenen Text.",
       "Auf ca. 120–160 Zeichen ausbauen: Inhalt der Seite und Nutzen für den Leser.")
def meta_desc_zu_kurz(conn, crawl_id):
    return abfrage(conn, f"SELECT id, length(meta_description) || ' Zeichen' FROM seiten WHERE crawl_id=? AND {HTML}"
                         f" AND length(meta_description) BETWEEN 1 AND {META_DESC_MIN - 1}", crawl_id)


@check("meta_desc_fehlt", "Meta-Description fehlt", "warning", "inhalt",
       "Ohne Beschreibung wählt die Suchmaschine selbst einen Textausschnitt.",
       "Kurze, einladende Beschreibung (ca. 120–160 Zeichen) ergänzen.")
def meta_desc_fehlt(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND COALESCE(meta_description, '') = ''", crawl_id)


@check("h1_fehlt", "H1-Überschrift fehlt", "warning", "inhalt",
       "Die H1 zeigt Nutzern und Suchmaschinen das Thema der Seite.",
       "Eine aussagekräftige H1 pro Seite setzen.")
def h1_fehlt(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND h1_anzahl = 0", crawl_id)


@check("h1_gleich_title", "Überschrift (H1) und Seitentitel identisch", "warning", "inhalt",
       "Kein Fehler, aber verschenkt: Unterschiedliche Formulierungen decken mehr Suchvarianten ab.",
       "Formuliere die Überschrift auf der Seite etwas anders als den Seitentitel.")
def h1_gleich_title(conn, crawl_id):
    return abfrage(conn, f"SELECT id, title FROM seiten WHERE crawl_id=? AND {HTML} AND h1_anzahl = 1 AND lower(trim(h1_text)) = lower(trim(title))", crawl_id)


@check("mehrere_h1", "Mehr als eine H1", "notice", "inhalt",
       "Mehrere H1 verwässern die Struktur der Seite.",
       "Eine H1 behalten, weitere zu H2 machen.")
def mehrere_h1(conn, crawl_id):
    return abfrage(conn, f"SELECT id, h1_anzahl || ' × H1' FROM seiten WHERE crawl_id=? AND {HTML} AND h1_anzahl > 1", crawl_id)


@check("wenig_text", f"Wenig Text (< {WOERTER_MIN} Wörter im Hauptinhalt)", "warning", "inhalt",
       "Dünne Seiten ranken schlecht, weil sie wenig Antwort auf Suchanfragen geben. Gezählt wird nur der "
       "Hauptinhalt – Menü, Fußzeile und Cookie-Hinweis machen eine Seite nicht gehaltvoller.",
       "Inhalt ausbauen, mit einer ähnlichen Seite zusammenlegen oder (z. B. dünne Glossar-Seiten) auf noindex setzen.")
def wenig_text(conn, crawl_id):
    # Wörter im Hauptbereich (geo.woerter); ältere Crawls ohne GEO-Signale: ganze Seite
    return abfrage(conn, f"""SELECT id, n || ' Wörter' FROM (
        SELECT id, COALESCE(json_extract(geo, '$.woerter'), woerter) AS n FROM seiten WHERE crawl_id=? AND {HTML})
        WHERE n < {WOERTER_MIN}""", crawl_id)


@check("text_html_niedrig", "Viel Code, wenig Text (≤ 10 % Text)", "warning", "inhalt",
       "Weniger als 10 % der Seite ist lesbarer Text, der Rest ist Code. Oft ist der Inhalt dünn oder die Seite "
       "lädt unnötig viel.",
       "Ergänze Text. Bleibt der Wert niedrig, lass prüfen, welche eingebetteten Skripte und Styles überflüssig sind.")
def text_html_niedrig(conn, crawl_id):
    return abfrage(conn, f"SELECT id, round(text_anteil * 100, 1) || ' %' FROM seiten WHERE crawl_id=? AND {HTML} AND text_anteil <= {TEXT_ANTEIL_MIN}", crawl_id)


@check("bilder_ohne_alt", "Bilder ohne alt-Attribut", "warning", "inhalt",
       "alt-Texte helfen Screenreadern und der Bildersuche.",
       "Jedem inhaltlichen Bild einen beschreibenden alt-Text geben (dekorative: alt=\"\").")
def bilder_ohne_alt(conn, crawl_id):
    return abfrage(conn, """
        SELECT seite_id, COUNT(*) || ' Bild(er)' FROM links
        WHERE crawl_id=? AND art='img' AND alt IS NULL GROUP BY seite_id""", crawl_id)
