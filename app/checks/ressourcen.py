"""Checks: JavaScript- und CSS-Dateien (Größe, Anzahl, Kompression, Caching, Minifizierung)."""

from app.checks.katalog import abfrage, check, json_spalte

JS_CSS_MAX_BYTES = 2 * 1024 * 1024
JS_CSS_MAX_ANZAHL = 100
CACHE_KURZ_SEKUNDEN = 7 * 24 * 3600   # Lighthouse empfiehlt für statische Dateien lange Cache-Zeiten
CSS_BLOCKIEREND_AB_ANZAHL = 3          # ein, zwei Stylesheets sind normal und nötig
CSS_BLOCKIEREND_AB_BYTES = 100 * 1024
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


@check("js_css_cache_kurz", "JS und CSS nur kurz gecacht (< 7 Tage)", "notice", "performance",
       "Der Browser darf die Dateien behalten, aber nur kurz. Wer nach ein paar Tagen wiederkommt, lädt alles neu. "
       "Lighthouse empfiehlt für statische Dateien lange Cache-Zeiten.",
       "Cache-Control mit langem max-age setzen (z. B. ein Jahr) und Dateinamen bei Änderungen wechseln. Manche "
       "Hoster (z. B. GitHub Pages) lassen das nicht zu, dann ist es kein Handlungsbedarf.")
def js_css_cache_kurz(conn, crawl_id):
    return abfrage(conn, _DATEIEN_JE_SEITE.format(
        bedingung=f"r.gecacht = 1 AND r.cache_sekunden IS NOT NULL AND r.cache_sekunden < {CACHE_KURZ_SEKUNDEN}"), crawl_id)


@check("css_blockierend", "Viele oder große Stylesheets bremsen den Seitenaufbau", "notice", "performance",
       f"Stylesheets im <head> halten den Aufbau an, bis sie geladen sind. Bei ein, zwei kleinen Dateien ist das "
       f"normal und nötig. Ab {CSS_BLOCKIEREND_AB_ANZAHL} Dateien oder {CSS_BLOCKIEREND_AB_BYTES // 1024} KB CSS "
       "sehen Besucher spürbar länger eine leere Fläche.",
       "CSS zusammenfassen, Ungenutztes entfernen und nur das für den ersten Bildschirm nötige CSS direkt laden. "
       "Bei WordPress hilft ein Optimierungs-Plugin.")
def css_blockierend(conn, crawl_id):
    treffer = []
    for seite_id, _, urls in json_spalte(conn, crawl_id, "css_blockierend", "css_blockierend != '[]'"):
        groesse = (conn.execute(f"SELECT COALESCE(SUM(bytes), 0) FROM ressourcen WHERE crawl_id=? AND url IN "
                                   f"({','.join('?' * len(urls))})", (crawl_id, *urls)).fetchone()[0]) if urls else 0
        if len(urls) >= CSS_BLOCKIEREND_AB_ANZAHL or groesse >= CSS_BLOCKIEREND_AB_BYTES:
            treffer.append((seite_id, f"{len(urls)} Datei(en), {groesse // 1024} KB"))
    return treffer

