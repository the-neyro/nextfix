"""Checks: Sitemap-Dateien und -Einträge."""

from app.checks.katalog import check
from app.crawler.sitemap import MAX_BYTES, MAX_URLS_PRO_DATEI
from app.crawler.urls import host, ist_intern


def _eintraege(conn, crawl_id) -> list[dict]:
    """Interne Sitemap-URLs mit effektivem Status (aus Crawl oder Nachprüfung) und Seitendaten."""
    start_host = host(conn.execute("SELECT start_url FROM crawls WHERE id=?", (crawl_id,)).fetchone()[0])
    zeilen = conn.execute("""
        SELECT e.url, COUNT(*) AS anzahl, MAX(e.status_code) AS status_nachpruefung,
               s.id AS seite_id, s.status_code, s.canonical, s.meta_robots, s.x_robots_tag, s.blockiert
        FROM sitemap_eintraege e LEFT JOIN seiten s ON s.crawl_id = e.crawl_id AND s.url = e.url
        WHERE e.crawl_id=? GROUP BY e.url""", (crawl_id,)).fetchall()
    ergebnis = []
    for z in zeilen:
        d = dict(z)
        if not ist_intern(d["url"], start_host):
            continue
        d["status"] = d["status_code"] if d["seite_id"] else d["status_nachpruefung"]
        ergebnis.append(d)
    return ergebnis


def _treffer(d: dict, grund: str):
    """Gecrawlte Seite → seite_id; sonst URL ins Detail (Seite ist nicht in der Seitenliste)."""
    return (d["seite_id"], grund) if d["seite_id"] else (None, f"{d['url']} – {grund}")


@check("sitemap_formatfehler", "Formatfehler in sitemap.xml", "error", "crawlbarkeit",
       "Suchmaschinen können eine fehlerhafte Sitemap nicht oder nur teilweise lesen.",
       "Sitemap gegen das Schema von sitemaps.org prüfen und korrigieren.")
def sitemap_formatfehler(conn, crawl_id):
    return [(None, f"{z[0]}: {z[1]}") for z in conn.execute(
        "SELECT url, fehler FROM sitemap_dateien WHERE crawl_id=? AND status=200 AND fehler IS NOT NULL", (crawl_id,))]


@check("sitemap_zu_gross", "sitemap.xml zu groß", "error", "crawlbarkeit",
       "Über 50 MB (unkomprimiert) oder 50.000 URLs ignorieren Suchmaschinen den Rest der Datei.",
       "Sitemap aufteilen und über einen Sitemap-Index verbinden.")
def sitemap_zu_gross(conn, crawl_id):
    return [(None, f"{z[0]}: {z[1] // 1024 // 1024} MB, {z[2]} URLs") for z in conn.execute(
        "SELECT url, bytes, url_anzahl FROM sitemap_dateien WHERE crawl_id=? AND (bytes > ? OR url_anzahl > ?)",
        (crawl_id, MAX_BYTES, MAX_URLS_PRO_DATEI))]


@check("sitemap_falsche_seiten", "Falsche Seiten in sitemap.xml", "error", "crawlbarkeit",
       "Die Sitemap ist die Liste, mit der du Google deine Seiten meldest. Stehen dort Adressen, die weiterleiten, "
       "fehlen, doppelt sind oder für Google ausgeblendet sind, verschwendet Google Zeit und vertraut der Liste weniger.",
       "Nimm diese Adressen aus der Sitemap: Weiterleitungen ersetzt du durch die Adresse, auf die sie zeigen, fehlende "
       "und ausgeblendete Seiten kommen ganz raus. Meist baut ein Plugin die Sitemap selbst, dann reicht es, die "
       "Ursache zu beheben (alte Seite löschen oder richtig weiterleiten).",
       wordpress="Yoast und Rank Math bauen die Sitemap selbst und lassen ausgeblendete Seiten weg. Steht trotzdem eine "
       "alte Adresse drin, ist die alte Seite meist noch veröffentlicht, obwohl eine Weiterleitung auf sie zeigt: in "
       "den Papierkorb legen.")
def sitemap_falsche_seiten(conn, crawl_id):
    treffer = []
    for d in _eintraege(conn, crawl_id):
        gruende = []
        if d["status"] is not None and d["status"] != 200:
            gruende.append(f"Status {d['status']}")
        if d["canonical"] and d["canonical"] != d["url"]:
            gruende.append(f"Canonical auf {d['canonical']}")
        if "noindex" in (d["meta_robots"] or "") or "noindex" in (d["x_robots_tag"] or "").lower():
            gruende.append("noindex")
        if d["anzahl"] > 1:
            gruende.append(f"{d['anzahl']}× in Sitemap")
        if gruende:
            treffer.append(_treffer(d, ", ".join(gruende)))
    return treffer


@check("sitemap_http_bei_https", "HTTP-URLs in sitemap.xml einer HTTPS-Website", "warning", "https",
       "Suchmaschinen müssen jeder HTTP-URL erst per Weiterleitung folgen.",
       "In der Sitemap nur die https://-Adressen verwenden.")
def sitemap_http_bei_https(conn, crawl_id):
    start = conn.execute("SELECT start_url FROM crawls WHERE id=?", (crawl_id,)).fetchone()[0]
    if not start.startswith("https://"):
        return []
    z = conn.execute("SELECT COUNT(*), MIN(url) FROM sitemap_eintraege WHERE crawl_id=? AND url LIKE 'http://%'",
                     (crawl_id,)).fetchone()
    return [(None, f"{z[0]} URL(s), z. B. {z[1]}")] if z[0] else []


@check("orphan_sitemap", "Verwaiste Seiten (nur in der Sitemap)", "notice", "links",
       "Die Seite steht in der Sitemap, wird aber von keiner anderen Seite verlinkt.",
       "Seite intern verlinken oder, falls nicht mehr gebraucht, aus der Sitemap entfernen.")
def orphan_sitemap(conn, crawl_id):
    if conn.execute("SELECT quelle FROM crawls WHERE id=?", (crawl_id,)).fetchone()[0] == "sitemap":
        return []  # ohne Link-Verfolgung ist "nicht verlinkt" nicht aussagekräftig
    verlinkt = {z[0] for z in conn.execute(
        "SELECT DISTINCT l.ziel_url FROM links l JOIN seiten s ON s.id = l.seite_id"
        " WHERE l.crawl_id=? AND l.art='a' AND s.url != l.ziel_url", (crawl_id,))}
    start = conn.execute("SELECT start_url FROM crawls WHERE id=?", (crawl_id,)).fetchone()[0]
    return [_treffer(d, "kein interner Link") for d in _eintraege(conn, crawl_id)
            if d["status"] == 200 and d["url"] not in verlinkt and d["url"] != start]
