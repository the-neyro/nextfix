"""Messdaten, die einen verschwundenen Treffer als nachgeprüft belegen."""

from functools import cached_property
from urllib.parse import urlsplit

from app.checks import inhalt, international, ladezeit, sitemap
from app.checks.katalog import GERENDERT, HTML, fakten, url_status
from app.crawler.crawler import MAX_HTML_BYTES
from app.crawler.filter import liste
from app.crawler.robots import RobotsTxt
from app.crawler.sitemap import MAX_DATEIEN, MAX_EINTRAEGE

_INHALT = {
    "title_fehlt", "title_doppelt", "title_zu_lang", "title_zu_kurz", "meta_desc_fehlt",
    "meta_desc_doppelt", "meta_desc_zu_lang", "meta_desc_zu_kurz", "h1_fehlt", "h1_gleich_title",
    "mehrere_h1", "wenig_text", "text_html_niedrig", "duplicate_content",
}
_DUPLIKATE = {"title_doppelt", "meta_desc_doppelt", "duplicate_content"}
_GEO = {"ki_fragen_ohne_faq", "ki_ohne_belege", "ki_textwand", "ki_artikel_ohne_autor_datum"}
_HTML = {
    "bilder_ohne_alt", "mixed_content", "https_verlinkt_http", "interne_links_nofollow", "zu_viele_links",
    "link_url_zu_lang", "links_ohne_anker", "nichtssagender_anker", "externe_nofollow", "unterstriche_url",
    "viewport_fehlt", "viewport_unvollstaendig", "meta_refresh", "mehrere_canonicals", "ohne_lang",
    "ohne_charset", "ohne_doctype", "frames", "passwort_ohne_https", "zu_viele_js_css",
}
_HTML_MERKMAL = {
    "link_syntax_fehler": "kaputte_links", "markup_fehlerhaft": "markup", "veraltete_plugins": "plugins",
    "h1_fehlt": "h1_anzahl", "mehrere_h1": "h1_anzahl", "h1_gleich_title": "h1_anzahl",
    "text_html_niedrig": "text_anteil", "canonical_defekt": "canonical_anzahl",
    "bilder_ohne_masse": "bilder_ohne_masse", "skripte_blockierend": "blockierend",
    "ki_ohne_hauptbereich": "semantik", "ki_schwer_lesbar": "lesbarkeit",
    "hreflang_code_ungueltig": "hreflang", "hreflang_relativ": "hreflang",
    "hreflang_ohne_selbstbezug": "hreflang", "hreflang_doppelt": "hreflang",
    "hreflang_lang_konflikt": "hreflang", "css_blockierend": "css_blockierend",
}
_RESSOURCEN = {
    "interne_bilder_defekt": (("img",), True),
    "interne_js_css_defekt": (("script", "css"), True),
    "externe_bilder_defekt": (("img",), False),
    "externe_js_css_defekt": (("script", "css"), False),
    "externe_links_defekt": (("a",), False),
    "js_css_zu_gross": (("script", "css"), True),
    "js_css_unkomprimiert": (("script", "css"), True),
    "js_css_ohne_cache": (("script", "css"), True),
    "js_css_nicht_minifiziert": (("script", "css"), True),
    "js_css_cache_kurz": (("script", "css"), True),
    "css_blockierend": (("css",), True),
}
_ROBOTS = {"robots_fehlt", "robots_formatfehler", "robots_unbekannte_felder", "sitemap_nicht_in_robots",
           "ki_bots_blockiert", "ki_training_bots_blockiert"}


class Nachpruefung:
    """Beleg pro Check. Kann die Datenbank ihn nicht liefern, bleibt der Befund offen."""

    def __init__(self, conn, jetzt, vorher):
        self.conn, self.jetzt, self.vorher = conn, jetzt, vorher

    @cached_property
    def daten(self):
        return self.conn.execute(
            "SELECT robots_status, robots_text, sitemap_status, quelle, checks_aus FROM crawls WHERE id=?",
            (self.jetzt["id"],)).fetchone()

    @cached_property
    def seiten(self):
        """Daten zu früheren Fundstellen für den Vergleich. Ältere Crawls können Merkmale offen lassen."""
        return {z["url"]: z for z in self.conn.execute(f"""
            SELECT url, id, tiefe, status_code, blockiert, abruf_fehler, ladezeit_ms, html_bytes,
                   woerter_roh, js_app, canonical, canonical_anzahl, h1_anzahl, text_anteil, geo, signatur, markup,
                   semantik, lesbarkeit, hreflang, kaputte_links, plugins, bilder_ohne_masse, blockierend,
                   css_blockierend,
                   ({HTML}) AS html, ({GERENDERT}) AS gerendert,
                   ({inhalt.INDEXIERBAR}) AS indexierbar, ({inhalt.KANONISCH}) AS kanonisch
            FROM seiten WHERE crawl_id=? AND url IN (
                SELECT s.url FROM issues i JOIN seiten s ON s.id=i.seite_id WHERE i.crawl_id=?
            )""", (self.jetzt["id"], self.vorher["id"]))}

    @cached_property
    def ausschluesse(self):
        return set(liste(self.daten["checks_aus"]))

    @cached_property
    def status(self):
        return url_status(self.conn, self.jetzt["id"])

    @cached_property
    def ressourcen(self):
        return {z["url"]: z for z in self.conn.execute(
            "SELECT url, status_code, bytes, extern FROM ressourcen WHERE crawl_id=?", (self.jetzt["id"],))}

    @cached_property
    def links(self):
        seiten_ids = {s["id"] for s in self.seiten.values()}
        ergebnis = {}
        for seite_id, url, art, intern in self.conn.execute(
                "SELECT seite_id, ziel_url, art, intern FROM links WHERE crawl_id=?", (self.jetzt["id"],)):
            if seite_id in seiten_ids:
                ergebnis.setdefault(seite_id, []).append((url, art, intern))
        return ergebnis

    @cached_property
    def hreflang(self):
        return {url: {ziel for _, ziel, _ in eintraege}
                for _, url, eintraege in international._eintraege(self.conn, self.jetzt["id"])}

    @cached_property
    def duplikate(self):
        gruppen = {}
        for check_id, url in self.conn.execute("""
                SELECT i.check_id, s.url FROM issues i JOIN seiten s ON s.id=i.seite_id
                WHERE i.crawl_id=? AND i.check_id IN ('title_doppelt', 'meta_desc_doppelt', 'duplicate_content')
                """, (self.vorher["id"],)):
            gruppen.setdefault(check_id, set()).add(url)
        return gruppen

    @cached_property
    def messwerte(self):
        return ladezeit.messwerte(self.conn, self.jetzt["id"])

    @cached_property
    def sitemap_dateien(self):
        return {z["url"]: z for z in self.conn.execute(
            "SELECT url, status, fehler, ist_index, url_anzahl FROM sitemap_dateien WHERE crawl_id=?",
            (self.jetzt["id"],))}

    @cached_property
    def sitemap_eintraege(self):
        return {z["url"]: z for z in sitemap._eintraege(self.conn, self.jetzt["id"])}

    @cached_property
    def fakten(self):
        return fakten(self.conn, self.jetzt["id"])

    def _html(self, seite):
        return (seite["html"] and seite["gerendert"]
                and (seite["html_bytes"] is None or seite["html_bytes"] <= MAX_HTML_BYTES)
                and (seite["woerter_roh"] is not None if self.jetzt["js_rendern"]
                     else not (self.vorher["js_rendern"] or seite["js_app"])))

    def _html_fuer(self, check_id, url):
        seite = self.seiten.get(url)
        if not seite or seite["blockiert"] or seite["abruf_fehler"] or not self._html(seite):
            return False
        if check_id in _INHALT | _GEO and not seite["indexierbar"]:
            return False
        if check_id in _DUPLIKATE and not seite["kanonisch"]:
            return False
        if check_id in _GEO:
            return seite["geo"] is not None
        merkmal = _HTML_MERKMAL.get(check_id)
        return merkmal is None or seite[merkmal] is not None

    def bestaetigt(self, check_id, url):
        if self.jetzt["status"] != "fertig" or check_id in self.ausschluesse:
            return False
        if url is None:
            return self._website(check_id)
        seite = self.seiten.get(url)
        if not seite or seite["blockiert"] or seite["abruf_fehler"]:
            return False
        code = seite["status_code"]
        antwort_ok = code is not None and 200 <= code < 300
        if check_id in {"status_4xx", "status_5xx", "perm_redirect"}:
            return antwort_ok
        if check_id == "nicht_erreichbar":
            return antwort_ok and seite["ladezeit_ms"] is not None
        if check_id in {"temp_redirect", "redirect_kette"}:
            if antwort_ok:
                return True
            return self._redirect_gemessen(url)
        if check_id in {"html_zu_gross", "unkomprimiert", "langsame_seite", "x_robots_noindex"}:
            return antwort_ok and seite["html"] and (
                check_id != "langsame_seite" or (
                    seite["ladezeit_ms"] is not None and seite["ladezeit_ms"] <= 5000))
        if check_id in {"url_zu_lang", "zu_viele_parameter"}:
            return antwort_ok
        if not self._html_fuer(check_id, url):
            return False
        if check_id in ladezeit.STICHPROBE:
            return self.messwerte.get(url, {}).get(check_id.removeprefix("ladezeit_")) is not None
        if check_id in _DUPLIKATE:
            # Die alte Vergleichsgruppe muss wieder im Datensatz sein, sonst kann ein Duplikat nur wegen der Stichprobe fehlen.
            return all(self._html_fuer(check_id, alt) and
                       (check_id != "duplicate_content" or self.seiten[alt]["signatur"] is not None)
                       for alt in self.duplikate[check_id])
        if check_id in _RESSOURCEN:
            return self._ressourcen_gemessen(check_id, seite)
        if check_id == "interne_links_defekt":
            return all(self.status.get(ziel) is not None for ziel, art, intern in self.links.get(seite["id"], ())
                       if art == "a" and intern)
        if check_id == "canonical_defekt":
            return seite["canonical"] in (None, url) or self.status.get(seite["canonical"]) == 200
        if check_id == "hreflang_ziel_defekt":
            return seite["hreflang"] is not None and all(self.status.get(ziel) == 200
                                                        for ziel in self.hreflang.get(url, ()))
        if check_id == "hreflang_ohne_rueckverweis":
            return seite["hreflang"] is not None and all(
                ziel == url or url in self.hreflang.get(ziel, ()) for ziel in self.hreflang.get(url, ()))
        if check_id in {"js_rendern_fehlgeschlagen", "inhalt_nur_per_js"}:
            return self.jetzt["js_rendern"] and seite["woerter_roh"] is not None
        if check_id == "js_app_ohne_rendern":
            return not self.jetzt["js_rendern"] or seite["woerter_roh"] is not None
        if check_id == "blockiert":
            return self._robots_erlaubt(url) and seite["indexierbar"]
        if check_id == "sitemap_falsche_seiten":
            return self.sitemap_gemessen
        if check_id == "klicktiefe":
            return self.daten["quelle"] == "website" or (self.daten["quelle"] == "beides" and seite["tiefe"] > 0)
        if check_id == "nur_ein_eingehender_link":
            return seite["tiefe"] > 0 and seite["kanonisch"] and self.eingehende_links.get(url, 0) >= 2
        if check_id == "orphan_sitemap":
            return self.daten["quelle"] != "sitemap" and self.eingehende_links.get(url, 0) > 0
        return check_id in _HTML | _INHALT | _GEO or check_id in _HTML_MERKMAL

    @cached_property
    def eingehende_links(self):
        return dict(self.conn.execute("""
            SELECT l.ziel_url, COUNT(DISTINCT l.seite_id) FROM links l JOIN seiten s ON s.id=l.seite_id
            WHERE l.crawl_id=? AND l.art='a' AND l.intern=1 AND s.url!=l.ziel_url AND s.render_fehler IS NULL
            GROUP BY l.ziel_url
            """, (self.jetzt["id"],)))

    @cached_property
    def robots(self):
        if self.daten["robots_status"] == 200 and self.daten["robots_text"] is not None:
            robots = RobotsTxt()
            robots.parse(self.daten["robots_text"].splitlines())
            return robots
        if self.daten["robots_status"] in (404, 410):
            return RobotsTxt()
        return None

    def _robots_erlaubt(self, url):
        return self.robots is not None and self.robots.can_fetch("Googlebot", url)

    @cached_property
    def redirect_ziele(self):
        return dict(self.conn.execute("SELECT url, redirect_ziel FROM seiten WHERE crawl_id=? AND redirect_ziel IS NOT NULL",
                                      (self.jetzt["id"],)))

    def _redirect_gemessen(self, url):
        gesehen = set()
        while url in self.redirect_ziele and url not in gesehen:
            gesehen.add(url)
            url = self.redirect_ziele[url]
        code = self.status.get(url)
        return url not in gesehen and code is not None and 200 <= code < 300

    def _ressourcen_gemessen(self, check_id, seite):
        arten, intern = _RESSOURCEN[check_id]
        for url, art, link_intern in self.links.get(seite["id"], ()):
            if art not in arten or link_intern != intern:
                continue
            ressource = self.ressourcen.get(url)
            if not ressource or ressource["extern"] == intern:
                return False
            code = ressource["status_code"]
            if code is None or not 200 <= code < 400:
                return False
            if check_id.startswith("js_css_") and ressource["bytes"] is None:
                return False
        return True

    @cached_property
    def sitemap_gemessen(self):
        # Ohne alte Dateien in der neuen Stichprobe ist eine verschwundene Meldung nicht belegbar.
        alte_dateien = {z[0] for z in self.conn.execute(
            "SELECT url FROM sitemap_dateien WHERE crawl_id=?", (self.vorher["id"],))}
        dateien = self.sitemap_dateien
        return (0 < len(dateien) < MAX_DATEIEN and alte_dateien <= dateien.keys()
                and sum(z["url_anzahl"] for z in dateien.values() if not z["ist_index"]) <= MAX_EINTRAEGE
                and all(z["status"] == 200 and z["fehler"] is None for z in dateien.values()))

    def _website(self, check_id):
        if urlsplit(self.jetzt["start_url"]).netloc != urlsplit(self.vorher["start_url"]).netloc:
            return False
        if check_id in _ROBOTS:
            return self.daten["robots_status"] == 200 and self.daten["robots_text"] is not None
        if check_id == "sitemap_fehlt":
            return self.daten["sitemap_status"] == 200 and self.sitemap_gemessen
        if check_id in {"sitemap_formatfehler", "sitemap_zu_gross", "sitemap_http_bei_https"}:
            return self.sitemap_gemessen and (
                check_id != "sitemap_http_bei_https" or self.jetzt["start_url"].startswith("https://"))
        if check_id == "sitemap_falsche_seiten":
            return self.sitemap_gemessen and all(z["status"] is not None and not z["blockiert"]
                                                  for z in self.sitemap_eintraege.values())
        if check_id in {"http_nicht_auf_https", "www_aufloesung"}:
            name = "http_zu_https" if check_id == "http_nicht_auf_https" else "www"
            messung = self.fakten.get(name) or {}
            code = messung.get("status")
            return (messung.get("ok") and code is not None and 200 <= code < 400 and
                    (check_id != "www_aufloesung" or self._redirect_gemessen(self.jetzt["start_url"])))
        tls = self.fakten.get("tls") or {}
        if check_id == "zertifikat_ablauf":
            return tls.get("rest_tage") is not None
        if check_id == "zertifikat_name":
            return tls.get("name_ok") is True and not tls.get("fehler")
        if check_id == "tls_veraltet":
            return tls.get("alt_erlaubt") is False and not tls.get("fehler")
        if check_id == "startseite_ohne_https":
            return self.jetzt["start_url"].startswith("https://") and self.status.get(self.jetzt["start_url"]) == 200
        if check_id == "ohne_last_modified":
            return self._header_stichprobe()
        if check_id == "kein_hsts":
            return self._hsts_gemessen()
        llms = self.fakten.get("llms") or {}
        if check_id in {"llms_fehlt", "llms_format", "llms_duenn", "llms_tote_links"}:
            if llms.get("status") != 200 or "format_ok" not in llms:
                return False
            if check_id == "llms_tote_links":
                return (llms.get("links_anzahl") == len(llms.get("links", ())) and
                        all(self.status.get(url) is not None for url in llms.get("links", ())))
            return check_id != "llms_duenn" or ("links_anzahl" in llms and llms["format_ok"])
        return False

    def _header_stichprobe(self):
        return bool(self.conn.execute(f"""
            SELECT COUNT(*) > 0 AND COUNT(*) = COUNT(neu.id)
            FROM (SELECT url FROM seiten WHERE crawl_id=? AND {HTML}) alt
            LEFT JOIN (SELECT id, url FROM seiten WHERE crawl_id=? AND {HTML}) neu ON neu.url=alt.url
            """, (self.vorher["id"], self.jetzt["id"])).fetchone()[0])

    def _hsts_gemessen(self):
        # Der Check wählt nur eine HTTPS-URL. Beim Wechsel der Stichprobe bleibt der alte Header ungeprüft.
        sql = ("SELECT url, hat_hsts FROM seiten WHERE crawl_id=? AND url LIKE 'https://%' "
               "AND status_code=200 ORDER BY tiefe, id LIMIT 1")
        vorher = self.conn.execute(sql, (self.vorher["id"],)).fetchone()
        jetzt = self.conn.execute(sql, (self.jetzt["id"],)).fetchone()
        return vorher is not None and jetzt is not None and vorher["url"] == jetzt["url"] and jetzt["hat_hsts"] == 1
