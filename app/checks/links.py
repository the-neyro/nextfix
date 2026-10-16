"""Checks: interne/externe Links und Anchor-Texte."""

from app.checks.katalog import HTML, abfrage, check, json_spalte

NICHTSSAGEND = (
    "hier", "mehr", "klicken sie hier", "hier klicken", "weiter", "weiterlesen", "mehr erfahren",
    "mehr lesen", "link", "click here", "here", "more", "read more", "learn more",
)
MAX_LINKS = 3000
MAX_PARAMETER = 4

# Ziel-URL eines Links → gecrawlte Seite mit Fehlerstatus
_DEFEKT = """
    SELECT l.seite_id, l.ziel_url || ' (' || COALESCE(s.status_code, 'nicht erreichbar') || ')'
    FROM links l JOIN seiten s ON s.crawl_id = l.crawl_id AND s.url = l.ziel_url
    WHERE l.crawl_id=? AND l.art='a' AND l.intern=1
      AND (s.status_code >= 400 OR (s.status_code IS NULL AND s.blockiert = 0))"""


@check("interne_links_defekt", "Defekte interne Links", "error", "links",
       "Links ins Leere frustrieren Nutzer und verschwenden Crawl-Budget.",
       "Link korrigieren oder entfernen, Zielseite ggf. umleiten.")
def interne_links_defekt(conn, crawl_id):
    return abfrage(conn, _DEFEKT, crawl_id)


@check("interne_links_nofollow", "Interne Links mit nofollow", "warning", "links",
       "nofollow auf eigenen Links bremst die Verteilung der Link-Stärke.",
       "nofollow von internen Links entfernen.")
def interne_links_nofollow(conn, crawl_id):
    return abfrage(conn, """
        SELECT seite_id, COUNT(*) || ' Link(s)' FROM links
        WHERE crawl_id=? AND art='a' AND intern=1 AND nofollow=1 GROUP BY seite_id""", crawl_id)


@check("zu_viele_links", f"Zu viele Links auf der Seite (> {MAX_LINKS})", "warning", "links",
       "Sehr viele Links verdünnen die Link-Stärke und wirken spammig.",
       "Navigation und Listen ausdünnen, Paginierung nutzen.")
def zu_viele_links(conn, crawl_id):
    return abfrage(conn, f"""
        SELECT seite_id, COUNT(*) || ' Links' FROM links WHERE crawl_id=? AND art='a'
        GROUP BY seite_id HAVING COUNT(*) > {MAX_LINKS}""", crawl_id)


@check("link_url_zu_lang", "Link-URL zu lang (> 2.000 Zeichen)", "warning", "links",
       "Überlange URLs werden von manchen Browsern und Servern nicht verarbeitet.",
       "URL kürzen, Parameter reduzieren.")
def link_url_zu_lang(conn, crawl_id):
    return abfrage(conn, "SELECT seite_id, substr(ziel_url, 1, 120) || '…' FROM links WHERE crawl_id=? AND length(ziel_url) > 2000", crawl_id)


@check("links_ohne_anker", "Links ohne Anchor-Text", "notice", "links",
       "Ohne Text wissen Nutzer und Suchmaschinen nicht, wohin der Link führt.",
       "Beschreibenden Linktext oder alt-Text am Link-Bild ergänzen.")
def links_ohne_anker(conn, crawl_id):
    return abfrage(conn, """
        SELECT seite_id, COUNT(*) || ' Link(s)' FROM links
        WHERE crawl_id=? AND art='a' AND COALESCE(anker_text, '') = '' GROUP BY seite_id""", crawl_id)


@check("nichtssagender_anker", "Nicht aussagekräftiger Anchor-Text", "notice", "links",
       "Texte wie „hier“ oder „mehr“ verraten nichts über das Ziel.",
       "Linktext beschreiben lassen, worum es auf der Zielseite geht.")
def nichtssagender_anker(conn, crawl_id):
    platzhalter = ",".join("?" * len(NICHTSSAGEND))
    return abfrage(conn, f"""
        SELECT seite_id, group_concat(DISTINCT anker_text) FROM links
        WHERE crawl_id=? AND art='a' AND lower(trim(anker_text)) IN ({platzhalter}) GROUP BY seite_id""",
        crawl_id, *NICHTSSAGEND)


@check("externe_nofollow", "Externe Links mit nofollow", "notice", "links",
       "Kein Fehler, aber prüfen, ob vertrauenswürdige Quellen wirklich nofollow brauchen.",
       "nofollow nur bei bezahlten oder nicht vertrauenswürdigen Links setzen.")
def externe_nofollow(conn, crawl_id):
    return abfrage(conn, """
        SELECT seite_id, COUNT(*) || ' Link(s)' FROM links
        WHERE crawl_id=? AND art='a' AND intern=0 AND nofollow=1 GROUP BY seite_id""", crawl_id)


@check("nur_ein_eingehender_link", "Nur ein eingehender interner Link", "notice", "links",
       "Schwach verlinkte Seiten bekommen wenig Link-Stärke und werden seltener gecrawlt.",
       "Seite aus thematisch passenden Seiten zusätzlich verlinken.")
def nur_ein_eingehender_link(conn, crawl_id):
    return abfrage(conn, """
        SELECT s.id, NULL FROM seiten s
        JOIN links l ON l.crawl_id = s.crawl_id AND l.ziel_url = s.url AND l.art = 'a' AND l.seite_id != s.id
        WHERE s.crawl_id=? AND s.status_code = 200 AND s.woerter IS NOT NULL AND s.tiefe > 0
          AND (s.canonical IS NULL OR s.canonical = s.url)  -- Varianten mit Canonical ausgenommen
        GROUP BY s.id HAVING COUNT(DISTINCT l.seite_id) = 1""", crawl_id)


@check("zu_viele_parameter", f"Zu viele URL-Parameter (> {MAX_PARAMETER})", "warning", "links",
       "Viele Parameter erzeugen Duplikate und verschwenden Crawl-Budget.",
       "Parameter reduzieren, sprechende URLs verwenden.")
def zu_viele_parameter(conn, crawl_id):
    treffer = []
    for seite_id, url in conn.execute("SELECT id, url FROM seiten WHERE crawl_id=? AND instr(url, '?') > 0", (crawl_id,)):
        anzahl = len([p for p in url.split("?", 1)[1].split("&") if p])
        if anzahl > MAX_PARAMETER:
            treffer.append((seite_id, f"{anzahl} Parameter"))
    return treffer


@check("unterstriche_url", "Unterstriche in der URL", "warning", "links",
       "Suchmaschinen trennen Wörter an Bindestrichen, nicht an Unterstrichen.",
       "Bindestriche statt Unterstrichen verwenden (mit 301 von alter URL).")
def unterstriche_url(conn, crawl_id):
    treffer = []
    for seite_id, url in conn.execute(f"SELECT id, url FROM seiten WHERE crawl_id=? AND {HTML}", (crawl_id,)):
        pfad = url.split("://", 1)[-1].split("/", 1)[-1].split("?", 1)[0]
        if "_" in pfad:
            treffer.append((seite_id, None))
    return treffer


@check("url_zu_lang", "URL länger als 200 Zeichen", "notice", "links",
       "Lange URLs sind schwer zu teilen und werden im Suchergebnis gekürzt.",
       "Kürzere, sprechende URLs verwenden.")
def url_zu_lang(conn, crawl_id):
    return abfrage(conn, "SELECT id, length(url) || ' Zeichen' FROM seiten WHERE crawl_id=? AND length(url) > 200", crawl_id)


@check("link_syntax_fehler", "Links mit fehlerhafter Syntax", "warning", "links",
       "Tippfehler im href (z. B. 'http:/', 'htp://', Leerzeichen) ergeben Links, die nirgendwohin führen.",
       "Die betroffenen href-Werte korrigieren.")
def link_syntax_fehler(conn, crawl_id):
    return [(seite_id, f"{len(hrefs)}×, z. B. {hrefs[0]}")
            for seite_id, _, hrefs in json_spalte(conn, crawl_id, "kaputte_links", "kaputte_links != '[]'")]
