"""Checks: Statuscodes, Erreichbarkeit, Redirects, robots.txt, Sitemap."""

from app.checks.katalog import HTML, abfrage, check
from app.crawler.robots import RobotsTxt

# Gecrawlte HTML-Seiten und solche, die Nextfix wegen robots.txt nicht abrufen durfte
HTML_ODER_GESPERRT = "(blockiert = 1 OR content_type LIKE '%html%')"

MAX_REDIRECTS = 3


@check("status_4xx", "Seiten mit 4xx-Statuscode", "error", "crawlbarkeit",
       "Die Adresse führt ins Leere („Seite nicht gefunden“). Besucher brechen ab, und Google nimmt die Seite aus den "
       "Suchergebnissen.",
       "Gibt es den Inhalt unter einer neuen Adresse, leite die alte Adresse dorthin weiter (eine dauerhafte "
       "Weiterleitung, auch „301“ genannt). Ist er ganz weg, entferne die Links, die noch auf die alte Adresse zeigen; "
       "welche das sind, zeigt die Aufgabe „Defekte interne Links“.",
       wordpress="Weiterleitung anlegen: kostenloses Plugin „Redirection“ oder Rank Math → Weiterleitungen (bei Yoast "
       "nur in der Premium-Version). Alte Adresse als Quelle, neue als Ziel, Typ „301“.")
def status_4xx(conn, crawl_id):
    return abfrage(conn, "SELECT id, status_code FROM seiten WHERE crawl_id=? AND status_code BETWEEN 400 AND 499", crawl_id)


@check("status_5xx", "Seiten mit 5xx-Statuscode", "error", "crawlbarkeit",
       "Serverfehler: Seite ist für alle nicht erreichbar.",
       "Server-Logs prüfen, Fehler im Backend beheben.")
def status_5xx(conn, crawl_id):
    return abfrage(conn, "SELECT id, status_code FROM seiten WHERE crawl_id=? AND status_code >= 500", crawl_id)


@check("nicht_erreichbar", "Seiten laden nicht oder zu langsam", "error", "crawlbarkeit",
       "Diese Seiten antworteten nicht innerhalb von 5 Sekunden oder gar nicht. Besucher und Google sehen nur eine "
       "Fehlermeldung.",
       "Öffne die Seiten selbst im Browser. Laden sie auch dort nicht, gib die Liste an deinen Hoster.")
def nicht_erreichbar(conn, crawl_id):
    return abfrage(conn, """
        SELECT id, COALESCE(abruf_fehler, 'Antwortzeit ' || ladezeit_ms || ' ms') FROM seiten
        WHERE crawl_id=? AND (abruf_fehler IS NOT NULL OR ladezeit_ms > 5000)""", crawl_id)


@check("redirect_kette", "Redirect-Ketten und -Schleifen", "error", "crawlbarkeit",
       f"Mehr als {MAX_REDIRECTS} Weiterleitungen hintereinander oder eine Schleife: Jede Station kostet Ladezeit, "
       "Schleifen enden nie. Googlebot folgt bis zu 10 Weiterleitungen, andere Crawler oft weniger.",
       "Jede Weiterleitung direkt auf das endgültige Ziel zeigen lassen.")
def redirect_kette(conn, crawl_id):
    ziele = dict(conn.execute(
        "SELECT url, redirect_ziel FROM seiten WHERE crawl_id=? AND redirect_ziel IS NOT NULL", (crawl_id,)))
    ids = dict(conn.execute("SELECT url, id FROM seiten WHERE crawl_id=?", (crawl_id,)))
    treffer = []
    for start in ziele:
        kette, url = [start], ziele[start]
        while url in ziele and url not in kette:
            kette.append(url)
            url = ziele[url]
        if url in kette:
            treffer.append((ids[start], "Schleife: " + " → ".join(kette + [url])))
        elif len(kette) > MAX_REDIRECTS:
            treffer.append((ids[start], f"{len(kette)} Redirects: " + " → ".join(kette + [url])))
    return treffer


@check("temp_redirect", "Temporäre Weiterleitungen", "warning", "crawlbarkeit",
       "302/307 signalisieren nur einen vorübergehenden Umzug. Google wertet das als schwächeres Signal für die neue "
       "Adresse; bei einem dauerhaften Umzug ist 301 eindeutiger.",
       "Bei dauerhaftem Umzug 301 verwenden.")
def temp_redirect(conn, crawl_id):
    return abfrage(conn, "SELECT id, status_code || ' → ' || redirect_ziel FROM seiten WHERE crawl_id=? AND status_code IN (302, 307)", crawl_id)


@check("perm_redirect", "Interne Links auf alte Adressen (dauerhafte Weiterleitung)", "notice", "crawlbarkeit",
       "Die Weiterleitung (301/308) selbst ist korrekt. Links auf die alte Adresse führen aber über einen Umweg "
       "zum Ziel – das kostet bei jedem Aufruf etwas Ladezeit.",
       "Ändere die internen Links so, dass sie direkt auf die neue Adresse zeigen.")
def perm_redirect(conn, crawl_id):
    # Nur Adressen, auf die ein interner Link zeigt: Zwischenschritte einer Kette meldet „Redirect-Ketten“
    return abfrage(conn, """
        SELECT s.id, s.status_code || ' → ' || s.redirect_ziel FROM seiten s
        WHERE s.crawl_id=? AND s.status_code IN (301, 308) AND EXISTS (
            SELECT 1 FROM links l WHERE l.crawl_id = s.crawl_id AND l.ziel_url = s.url AND l.art = 'a' AND l.intern = 1)""",
        crawl_id)


@check("robots_fehlt", "robots.txt nicht gefunden", "notice", "crawlbarkeit",
       "Ohne robots.txt fehlen Crawl-Regeln und der Verweis auf die Sitemap.",
       "robots.txt im Root anlegen, mindestens mit Sitemap-Zeile.")
def robots_fehlt(conn, crawl_id):
    z = conn.execute("SELECT robots_status FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    return [] if z[0] == 200 else [(None, f"Status {z[0]}")]


@check("sitemap_fehlt", "sitemap.xml nicht gefunden", "notice", "crawlbarkeit",
       "Die Sitemap hilft Suchmaschinen, alle wichtigen Seiten zu finden. Laut Google brauchen kleine, gut verlinkte "
       "Websites (bis etwa 500 Seiten) nicht unbedingt eine; schaden tut sie nie.",
       "sitemap.xml erzeugen und in robots.txt eintragen.")
def sitemap_fehlt(conn, crawl_id):
    z = conn.execute("SELECT sitemap_status FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    return [] if z[0] == 200 else [(None, f"Status {z[0]}")]


@check("sitemap_nicht_in_robots", "Sitemap nicht in robots.txt", "warning", "crawlbarkeit",
       "Suchmaschinen finden die Sitemap am zuverlässigsten über robots.txt.",
       "Zeile 'Sitemap: https://…/sitemap.xml' in robots.txt ergänzen.")
def sitemap_nicht_in_robots(conn, crawl_id):
    z = conn.execute("SELECT robots_status, sitemap_urls FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    return [(None, None)] if z[0] == 200 and not z[1] else []


@check("blockiert", "Seiten für Google gesperrt", "notice", "crawlbarkeit",
       "„noindex“: Die Seite erscheint nicht im Suchergebnis. robots.txt: Google darf die Seite nicht abrufen; sie "
       "kann trotzdem auftauchen, dann ohne Beschreibung. Geprüft wird die robots.txt so, wie Googlebot sie liest.",
       "Geh die Liste durch: Login, Warenkorb und Danke-Seiten dürfen gesperrt sein. Alles andere entsperren lassen. "
       "Soll eine Seite sicher nicht erscheinen, nimm „noindex“ statt robots.txt.")
def blockiert(conn, crawl_id):
    text = conn.execute("SELECT robots_text FROM crawls WHERE id=?", (crawl_id,)).fetchone()[0]
    robots = RobotsTxt()
    if text:
        robots.parse(text.splitlines())
    treffer = []
    for sid, url, meta in conn.execute(f"SELECT id, url, meta_robots FROM seiten WHERE crawl_id=? AND {HTML_ODER_GESPERRT}",
                                       (crawl_id,)):
        if not robots.can_fetch("Googlebot", url):
            treffer.append((sid, "robots.txt (für Googlebot)"))
        elif meta and "noindex" in meta.lower():
            treffer.append((sid, f"meta robots: {meta}"))
    return treffer


@check("x_robots_noindex", "noindex per X-Robots-Tag", "notice", "crawlbarkeit",
       "Der HTTP-Header schließt die Seite vom Index aus.",
       "Prüfen, ob das gewollt ist.")
def x_robots_noindex(conn, crawl_id):
    return abfrage(conn, "SELECT id, x_robots_tag FROM seiten WHERE crawl_id=? AND lower(x_robots_tag) LIKE '%noindex%'", crawl_id)


@check("klicktiefe", "Mehr als 3 Klicks von der Startseite", "notice", "crawlbarkeit",
       "Tief versteckte Seiten werden seltener gecrawlt und gelten als weniger wichtig.",
       "Wichtige Seiten aus Navigation oder Hub-Seiten verlinken.")
def klicktiefe(conn, crawl_id):
    return abfrage(conn, f"SELECT id, tiefe FROM seiten WHERE crawl_id=? AND {HTML} AND tiefe > 3", crawl_id)


@check("js_app_ohne_rendern", "Seite baut sich per JavaScript auf – ohne JavaScript geprüft", "warning", "crawlbarkeit",
       "Die Seite hat einen leeren App-Container (z. B. React oder Vue) und kaum Text im HTML. So sehen sie auch die "
       "Crawler der KI-Suchdienste. Die Prüfung lief ohne JavaScript, Inhalt und Links fehlen daher womöglich im Ergebnis.",
       "In den Einstellungen „JavaScript ausführen“ einschalten und erneut prüfen. Dauerhaft besser: Inhalte schon im "
       "HTML ausliefern (Server-Rendering oder statische Seiten).")
def js_app_ohne_rendern(conn, crawl_id):
    return abfrage(conn, """
        SELECT s.id, 'leerer Container ' || s.js_app || ', ' || s.woerter || CASE s.woerter WHEN 1 THEN ' Wort' ELSE ' Wörter' END
               || ' im HTML'
        FROM seiten s JOIN crawls c ON c.id = s.crawl_id
        WHERE s.crawl_id=? AND c.js_rendern = 0 AND s.status_code = 200 AND s.js_app IS NOT NULL
          AND s.woerter < 100""", crawl_id)


@check("inhalt_nur_per_js", "Inhalt entsteht erst per JavaScript", "warning", "crawlbarkeit",
       "Ohne JavaScript steht auf der Seite weniger als die Hälfte des Textes. Google rendert JavaScript, aber "
       "verzögert; die Crawler der KI-Suchdienste (ChatGPT, Perplexity, Claude) und viele andere führen es gar nicht "
       "aus und sehen eine fast leere Seite.",
       "Wichtige Inhalte schon im HTML ausliefern: Server-Rendering oder statische Seiten (z. B. Next.js/Nuxt mit "
       "SSR/SSG, Prerendering). Nur Komfort-Funktionen per JavaScript nachladen.")
def inhalt_nur_per_js(conn, crawl_id):
    # Nur bei Crawls mit „JavaScript ausführen“ ist woerter_roh gefüllt
    return abfrage(conn, f"""
        SELECT id, 'ohne JavaScript ' || woerter_roh || CASE woerter_roh WHEN 1 THEN ' Wort' ELSE ' Wörter' END
               || ', mit JavaScript ' || woerter
        FROM seiten WHERE crawl_id=? AND {HTML} AND woerter_roh IS NOT NULL
          AND woerter >= 50 AND woerter_roh * 2 < woerter""", crawl_id)


@check("js_rendern_fehlgeschlagen", "JavaScript ließ sich nicht ausführen – Inhalt ungeprüft", "warning", "crawlbarkeit",
       "Nextfix konnte die Seite nicht im Browser laden (z. B. Zeitlimit oder abgebrochene Verbindung) und hat nur das "
       "Roh-HTML gesehen. Titel, Text, Überschriften und Duplikate prüft Nextfix dort deshalb nicht, sonst gäbe es "
       "Fehlalarme aus dem leeren HTML. Scheitert es wiederholt, kann auch Googles Renderer Probleme haben.",
       "Erneut prüfen. Scheitert es wieder: Seite im Browser öffnen und auf Fehler oder sehr langes Laden achten. "
       "Dauerhaft robuster: Inhalte schon im HTML ausliefern (Server-Rendering oder statische Seiten).")
def js_rendern_fehlgeschlagen(conn, crawl_id):
    return abfrage(conn, "SELECT id, render_fehler FROM seiten WHERE crawl_id=? AND render_fehler IS NOT NULL", crawl_id)
