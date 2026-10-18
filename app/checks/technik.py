"""Checks: HTTPS, Performance, technisches Markup."""

from app.checks.katalog import HTML, abfrage, check, json_spalte

HTML_MAX_BYTES = 2 * 1024 * 1024


# ---------- HTTPS ----------

@check("mixed_content", "Unsichere Inhalte auf sicheren Seiten (Mixed Content)", "error", "https",
       "Die Seite läuft über HTTPS, lädt aber Bilder, Skripte oder Styles über HTTP. Browser blockieren sie oder "
       "zeigen eine Warnung.",
       "Ersetze in den Adressen dieser Dateien „http://“ durch „https://“.")
def mixed_content(conn, crawl_id):
    return abfrage(conn, """
        SELECT l.seite_id, COUNT(*) || ' Ressource(n), z. B. ' || MIN(l.ziel_url)
        FROM links l JOIN seiten s ON s.id = l.seite_id
        WHERE l.crawl_id=? AND s.url LIKE 'https://%' AND l.art != 'a' AND l.ziel_url LIKE 'http://%'
        GROUP BY l.seite_id""", crawl_id)


@check("startseite_ohne_https", "Startseite nutzt kein HTTPS", "warning", "https",
       "Ohne HTTPS warnt der Browser, und HTTPS ist ein Ranking-Signal.",
       "TLS-Zertifikat einrichten und HTTP per 301 auf HTTPS umleiten.")
def startseite_ohne_https(conn, crawl_id):
    z = conn.execute("SELECT start_url FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    return [(None, z[0])] if z[0].startswith("http://") else []


@check("https_verlinkt_http", "HTTPS-Seiten verlinken auf HTTP", "warning", "https",
       "Interne Links auf HTTP erzeugen unnötige Redirects oder unsichere Seitenaufrufe.",
       "Interne Links auf die HTTPS-Version umstellen.")
def https_verlinkt_http(conn, crawl_id):
    return abfrage(conn, """
        SELECT l.seite_id, COUNT(*) || ' Link(s)' FROM links l JOIN seiten s ON s.id = l.seite_id
        WHERE l.crawl_id=? AND s.url LIKE 'https://%' AND l.art='a' AND l.intern=1 AND l.ziel_url LIKE 'http://%'
        GROUP BY l.seite_id""", crawl_id)


@check("kein_hsts", "Browser erzwingen keine sichere Verbindung (HSTS)", "notice", "https",
       "Beim allerersten Aufruf kann die Verbindung noch unverschlüsselt sein und abgefangen werden.",
       "Lass deinen Hoster den Header „Strict-Transport-Security“ einschalten – eine Einstellung für die ganze Website.")
def kein_hsts(conn, crawl_id):
    z = conn.execute("SELECT hat_hsts FROM seiten WHERE crawl_id=? AND url LIKE 'https://%' AND status_code=200 ORDER BY tiefe, id LIMIT 1", (crawl_id,)).fetchone()
    return [(None, None)] if z and not z[0] else []


# ---------- Performance ----------

@check("html_zu_gross", "HTML zu groß (> 2 MB)", "error", "performance",
       "Große Seiten laden langsam, Crawler brechen evtl. ab.",
       "Inline-Daten, Skripte und Styles auslagern, HTML verschlanken.")
def html_zu_gross(conn, crawl_id):
    return abfrage(conn, f"SELECT id, (html_bytes / 1024) || ' KB' FROM seiten WHERE crawl_id=? AND {HTML} AND html_bytes > {HTML_MAX_BYTES}", crawl_id)


@check("langsame_seite", "Langsame Server-Antwort (HTML > 1,8 s)", "warning", "performance",
       "Gemessen wird nur, wie lange das HTML braucht. Laut web.dev ist eine Server-Antwort über 1,8 Sekunden "
       "schlecht; alles danach (Bilder, Skripte) kommt noch obendrauf.",
       "Server-Antwortzeit verbessern: Caching, schnellere Datenbank-Abfragen, CDN.")
def langsame_seite(conn, crawl_id):
    return abfrage(conn, f"SELECT id, ladezeit_ms || ' ms' FROM seiten WHERE crawl_id=? AND {HTML} AND ladezeit_ms > 1800 AND ladezeit_ms <= 5000", crawl_id)


@check("unkomprimiert", "Unkomprimierte Seiten", "warning", "performance",
       "Ohne gzip/brotli werden deutlich mehr Daten übertragen.",
       "Kompression auf dem Webserver aktivieren.")
def unkomprimiert(conn, crawl_id):
    return abfrage(conn, f"SELECT id, (html_bytes / 1024) || ' KB' FROM seiten WHERE crawl_id=? AND {HTML} AND content_encoding IS NULL", crawl_id)


# ---------- Defekte Ressourcen ----------

_RESSOURCE_DEFEKT = """
    SELECT l.seite_id, l.ziel_url || ' (' || COALESCE(r.status_code, 'nicht erreichbar') || ')'
    FROM links l JOIN ressourcen r ON r.crawl_id = l.crawl_id AND r.url = l.ziel_url
    WHERE l.crawl_id=? AND l.art IN ({arten}) AND r.extern = {extern} AND (r.status_code IS NULL OR r.status_code >= 400)"""


@check("interne_bilder_defekt", "Defekte interne Bilder", "error", "technik",
       "Fehlende Bilder wirken unprofessionell und fehlen in der Bildersuche.",
       "Pfad korrigieren oder Bild wieder hochladen.")
def interne_bilder_defekt(conn, crawl_id):
    return abfrage(conn, _RESSOURCE_DEFEKT.format(arten="'img'", extern=0), crawl_id)


@check("interne_js_css_defekt", "Defekte interne JS- und CSS-Dateien", "error", "technik",
       "Fehlende Skripte oder Styles können Darstellung und Funktion der Seite zerstören.",
       "Pfad korrigieren oder Datei wieder bereitstellen.")
def interne_js_css_defekt(conn, crawl_id):
    return abfrage(conn, _RESSOURCE_DEFEKT.format(arten="'script', 'css'", extern=0), crawl_id)


# ---------- Markup ----------

@check("viewport_fehlt", "Viewport-Tag fehlt", "error", "technik",
       "Ohne Viewport wird die Seite auf Smartphones winzig dargestellt; Google bewertet mobil.",
       '<meta name="viewport" content="width=device-width, initial-scale=1"> ergänzen.')
def viewport_fehlt(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND hat_viewport = 0", crawl_id)


@check("viewport_unvollstaendig", "Viewport ohne width/initial-scale", "error", "technik",
       "Viewport-Tag ist da, aber ohne Breite bzw. Skalierung wirkungslos.",
       'content="width=device-width, initial-scale=1" setzen.')
def viewport_unvollstaendig(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND hat_viewport = 1 AND viewport_ok = 0", crawl_id)


@check("meta_refresh", "Seite mit Meta-Refresh", "warning", "technik",
       "Google behandelt einen sofortigen Meta-Refresh wie eine Weiterleitung. Für Besucher ist er trotzdem "
       "langsam und irritierend, und andere Suchmaschinen verstehen ihn schlechter.",
       "Durch serverseitige 301-Weiterleitung ersetzen.")
def meta_refresh(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND hat_meta_refresh = 1", crawl_id)


@check("mehrere_canonicals", "Mehrere Canonical-URLs", "error", "technik",
       "Widersprüchliche Canonicals werden von Suchmaschinen ignoriert.",
       "Genau ein Canonical pro Seite setzen.")
def mehrere_canonicals(conn, crawl_id):
    return abfrage(conn, f"SELECT id, canonical_anzahl || ' Canonicals' FROM seiten WHERE crawl_id=? AND {HTML} AND canonical_anzahl > 1", crawl_id)


@check("canonical_defekt", "Hauptversion (Canonical) zeigt auf eine kaputte Seite", "error", "technik",
       "Der Canonical verweist auf eine Adresse, die einen Fehler liefert oder weiterleitet. Google ignoriert den "
       "Hinweis dann.",
       "Trag als Canonical die richtige, funktionierende Adresse ein – meist die Seite selbst.")
def canonical_defekt(conn, crawl_id):
    return abfrage(conn, """
        SELECT s.id, s.canonical || ' (' || COALESCE(z.status_code, 'nicht erreichbar') || ')'
        FROM seiten s JOIN seiten z ON z.crawl_id = s.crawl_id AND z.url = s.canonical
        WHERE s.crawl_id=? AND s.canonical IS NOT NULL AND s.canonical != s.url
          AND COALESCE(z.status_code, 0) != 200 AND z.blockiert = 0""", crawl_id)


@check("ohne_lang", "Kein lang-Attribut", "warning", "technik",
       "Ohne Sprachangabe lesen Screenreader den Text womöglich in der falschen Aussprache vor, und Browser bieten "
       "unnötig eine Übersetzung an. Google selbst erkennt die Sprache am Text und nutzt lang nicht.",
       '<html lang="de"> setzen.')
def ohne_lang(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND lang IS NULL", crawl_id)


@check("ohne_charset", "Keine Zeichenkodierung", "warning", "technik",
       "Ohne Kodierung können Umlaute falsch dargestellt werden.",
       '<meta charset="utf-8"> oder Content-Type mit charset setzen.')
def ohne_charset(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND hat_charset = 0", crawl_id)


@check("ohne_doctype", "Kein Doctype", "warning", "technik",
       "Ohne Doctype rendern Browser im Quirks-Modus.",
       "<!doctype html> an den Anfang setzen.")
def ohne_doctype(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND hat_doctype = 0", crawl_id)


@check("frames", "Seite mit Frames", "warning", "technik",
       "Inhalte in Frames werden schlecht indexiert.",
       "Frames durch normales Layout ersetzen.")
def frames(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND hat_frames = 1", crawl_id)


@check("passwort_ohne_https", "Passwortfeld auf HTTP-Seite", "error", "https",
       "Eingegebene Passwörter gehen unverschlüsselt über das Netz, Browser warnen deutlich.",
       "Seiten mit Login- oder Passwortfeld nur über HTTPS ausliefern.")
def passwort_ohne_https(conn, crawl_id):
    return abfrage(conn, f"SELECT id, NULL FROM seiten WHERE crawl_id=? AND {HTML} AND hat_passwort=1 AND url LIKE 'http://%'", crawl_id)


@check("veraltete_plugins", "Veraltete Browser-Plugins (Flash, Java, Silverlight)", "notice", "technik",
       "Diese Plugins laufen in aktuellen Browsern nicht mehr, der Inhalt bleibt für Nutzer und Crawler unsichtbar.",
       "Inhalte mit HTML5 (video, canvas, JavaScript) umsetzen.")
def veraltete_plugins(conn, crawl_id):
    return [(seite_id, ", ".join(sorted(set(tags))))
            for seite_id, _, tags in json_spalte(conn, crawl_id, "plugins", "plugins != '[]'")]


@check("ohne_last_modified", "Weder Last-Modified noch ETag", "notice", "technik",
       "Ohne Änderungsdatum (Last-Modified) oder Versionskennung (ETag) können Crawler nicht gezielt nur geänderte "
       "Seiten neu abrufen. Google kommt mit beidem zurecht und bevorzugt ETag.",
       "Server so einstellen, dass er den Header 'Last-Modified' (oder ein ETag) mitsendet.")
def ohne_last_modified(conn, crawl_id):
    # Meist eine Server-Einstellung für alle Seiten: ein Hinweis für die Website statt einer pro Seite
    fehlend, gesamt = conn.execute(
        f"SELECT SUM(COALESCE(last_modified, '') = '' AND COALESCE(etag, '') = ''), COUNT(*) FROM seiten WHERE crawl_id=? AND {HTML}", (crawl_id,)).fetchone()
    return [(None, f"{fehlend} von {gesamt} HTML-Seiten")] if fehlend else []
