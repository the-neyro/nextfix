"""Checks: JavaScript- und CSS-Dateien (Größe, Anzahl, Kompression, Caching, Minifizierung)."""

from app.checks.katalog import abfrage, check, json_spalte

JS_CSS_MAX_BYTES = 2 * 1024 * 1024
JS_CSS_MAX_ANZAHL = 100
KOMPRESSION_AB_BYTES = 1024     # winzige Dateien profitieren kaum von gzip

_DATEIEN_JE_SEITE = """
    SELECT l.seite_id, COUNT(DISTINCT r.url) || ' Datei(en), z. B. ' || MIN(r.url)
    FROM links l JOIN ressourcen r ON r.crawl_id = l.crawl_id AND r.url = l.ziel_url
    WHERE l.crawl_id=? AND l.art IN ('script', 'css') AND r.extern = 0 AND r.status_code = 200 AND {bedingung}
    GROUP BY l.seite_id"""


@check("js_css_zu_gross", "JS und CSS zusammen zu groß (> 2 MB)", "warning", "performance",
       "Je mehr Skript- und Style-Daten eine Seite braucht, desto später ist sie benutzbar, vor allem mobil.",
       "Ungenutzten Code entfernen, Dateien aufteilen und nur dort laden, wo sie gebraucht werden.")
def js_css_zu_gross(conn, crawl_id):
    return abfrage(conn, f"""
        SELECT seite_id, (summe / 1024) || ' KB' FROM (
            SELECT l.seite_id, SUM(r.bytes) AS summe
            FROM (SELECT DISTINCT seite_id, ziel_url FROM links WHERE crawl_id=? AND art IN ('script', 'css')) l
            JOIN ressourcen r ON r.crawl_id = ? AND r.url = l.ziel_url AND r.extern = 0
            GROUP BY l.seite_id)
        WHERE summe > {JS_CSS_MAX_BYTES}""", crawl_id, crawl_id)


@check("zu_viele_js_css", f"Zu viele JS- und CSS-Dateien (> {JS_CSS_MAX_ANZAHL})", "warning", "performance",
       "Jede Datei ist eine eigene Anfrage an den Server, viele davon bremsen den Seitenaufbau.",
       "Dateien bündeln und nicht benötigte Skripte und Styles entfernen.")
def zu_viele_js_css(conn, crawl_id):
    return abfrage(conn, f"""
        SELECT seite_id, COUNT(DISTINCT ziel_url) || ' Dateien' FROM links
        WHERE crawl_id=? AND art IN ('script', 'css')
        GROUP BY seite_id HAVING COUNT(DISTINCT ziel_url) > {JS_CSS_MAX_ANZAHL}""", crawl_id)


@check("js_css_unkomprimiert", "Unkomprimierte JS- und CSS-Dateien", "warning", "performance",
       "Ohne gzip oder Brotli überträgt der Server ein Vielfaches der nötigen Datenmenge.",
       "Kompression (gzip/Brotli) für JavaScript und CSS im Webserver einschalten.")
def js_css_unkomprimiert(conn, crawl_id):
    return abfrage(conn, _DATEIEN_JE_SEITE.format(
        bedingung=f"r.bytes > {KOMPRESSION_AB_BYTES} AND COALESCE(r.content_encoding, '') IN ('', 'identity')"), crawl_id)


@check("js_css_ohne_cache", "JS- und CSS-Dateien ohne Browser-Caching", "warning", "performance",
       "Ohne Cache-Angaben lädt der Browser dieselben Dateien bei jedem Seitenaufruf neu.",
       "Header 'Cache-Control: max-age=…' (oder Expires) für statische Dateien setzen.")
def js_css_ohne_cache(conn, crawl_id):
    return abfrage(conn, _DATEIEN_JE_SEITE.format(bedingung="r.gecacht = 0"), crawl_id)


@check("js_css_nicht_minifiziert", "Skript- und Style-Dateien nicht verkleinert", "notice", "performance",
       "Leerzeichen, Kommentare und Zeilenumbrüche machen die Dateien größer, die Seite lädt dadurch etwas langsamer.",
       "Aktiviere ein Optimierungs-Plugin (z. B. Autoptimize bei WordPress) oder lass die Dateien beim Build "
       "verkleinern (esbuild, cssnano).")
def js_css_nicht_minifiziert(conn, crawl_id):
    return abfrage(conn, _DATEIEN_JE_SEITE.format(bedingung="r.minifiziert = 0"), crawl_id)


@check("skripte_blockierend", "Skripte bremsen den Seitenaufbau", "notice", "performance",
       "Diese Skripte im <head> laden, bevor die Seite etwas zeigt (kein async oder defer). Besucher sehen länger "
       "eine leere Fläche.",
       "Lade Chat-Widget, Tracking und ähnliche Skripte später (Attribut „defer“) oder am Ende der Seite. "
       "Das kann deine Technik in Minuten.")
def skripte_blockierend(conn, crawl_id):
    return [(seite_id, f"{len(srcs)}: " + ", ".join(src.rsplit("/", 1)[-1][:40] for src in srcs[:3]))
            for seite_id, _, srcs in json_spalte(conn, crawl_id, "blockierend", "blockierend != '[]'")]
