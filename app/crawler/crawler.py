"""Crawler: Breitensuche ab Start-URL, speichert Seiten, Links und Ressourcen in der DB.

Bewusst synchron und sequenziell: einfach, höflich zum Server, gut testbar.
"""

import json
import sqlite3
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.crawler import filter, rendern, ressourcen, site, sitemap
from app.crawler.parser import dekodieren, zerlegen
from app.crawler.robots import RobotsTxt
from app.crawler.urls import host, ist_intern, ist_lokal, normalisieren

TIMEOUT = 15.0          # Sekunden; > 5 s Antwortzeit wird als Problem gewertet
MAX_RESSOURCEN = 2000   # Obergrenze für Bild/JS/CSS-Prüfungen pro Crawl
MAX_EXTERN = 500       # externe Links/Ressourcen pro Crawl
EXTERN_PAUSE = 0.1     # Sekunden; verschiedene Hosts, daher kürzer als die Crawl-Pause
MAX_SITEMAP_PRUEFUNG = 1000  # Sitemap-URLs, die nicht gecrawlt wurden, per HEAD prüfen
MAX_HTML_BYTES = 5 * 1024 * 1024   # mehr HTML wird nicht gelesen (Check „HTML zu groß“ greift ab 2 MB)
QUELLEN = ("website", "sitemap", "beides")
WIEDERHOLUNGEN = 2      # weitere Versuche nach Connect-/Read-Timeout, bevor etwas als nicht erreichbar zählt
WIEDERHOLEN_PAUSE = 2.0  # Sekunden zwischen den Versuchen
# Manche Server (z. B. Google-Hilfeseiten) antworten Bots mit 404/403; externe Links prüfen wir dann wie ein Browser nach
EXTERN_NACHPRUEFEN = (403, 404, 405, 429, 501)
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

# austauschbar für Tests (ohne Chromium)
RENDERER_FABRIK = rendern.Renderer


@dataclass
class CrawlEinstellungen:
    start_url: str
    seitenlimit: int = 500
    crawl_delay: float = 0.5
    user_agent: str = "SeoToolBot/0.1 (+lokal)"
    robots_beachten: bool = True
    quelle: str = "website"   # website = Links folgen, sitemap = nur Sitemap-URLs, beides = Links + danach
                              # Sitemap-URLs, die über Links nicht erreicht wurden (verwaiste Seiten mit prüfen)
    erlauben: str = ""        # Pfad-Masken, eine pro Zeile (app/crawler/filter.py)
    sperren: str = ""
    parameter_entfernen: str = ""
    js_rendern: bool = False  # Seiten zusätzlich in Chromium laden und das fertige DOM auswerten (app/crawler/rendern.py)


class Crawler:
    def __init__(self, conn: sqlite3.Connection, crawl_id: int, e: CrawlEinstellungen,
                 client: httpx.Client | None = None):
        self.conn = conn
        self.crawl_id = crawl_id
        self.e = e
        self.client = client or httpx.Client(
            timeout=TIMEOUT, follow_redirects=False, headers={"User-Agent": e.user_agent}
        )
        self.start_host = host(e.start_url)
        self.robots = RobotsTxt()   # ohne robots.txt: alles erlaubt
        self.sitemap_urls: list[str] = []
        self.filter = filter.UrlFilter(filter.liste(e.erlauben), filter.liste(e.sperren),
                                       filter.liste(e.parameter_entfernen))
        self.renderer: rendern.Renderer | None = None

    # ---------- Ablauf ----------

    def ausfuehren(self) -> None:
        self._robots_und_sitemap()
        if self.e.js_rendern:
            try:
                with RENDERER_FABRIK(self.e.user_agent) as self.renderer:
                    self._seiten_crawlen()
            except ImportError as fehler:
                raise RuntimeError("JavaScript ausführen braucht Playwright: .venv/bin/pip install -r requirements.txt"
                                   " && .venv/bin/playwright install chromium") from fehler
            finally:
                self.renderer = None
        else:
            self._seiten_crawlen()
        self._ressourcen_pruefen()
        self._extern_pruefen()
        self._sitemap_urls_pruefen()

    def _abbruch_gewuenscht(self) -> bool:
        zeile = self.conn.execute("SELECT abbrechen FROM crawls WHERE id = ?", (self.crawl_id,)).fetchone()
        return bool(zeile and zeile[0])

    def _fortschritt(self, **felder) -> None:
        """Fortschritt + Lebenszeichen speichern und committen."""
        setzen = "".join(f"{k}=?, " for k in felder)
        self.conn.execute(f"UPDATE crawls SET {setzen}lebenszeichen=datetime('now') WHERE id=?",
                          (*felder.values(), self.crawl_id))
        self.conn.commit()

    def _warten(self) -> None:
        if self.e.crawl_delay > 0:
            time.sleep(self.e.crawl_delay)

    # ---------- robots.txt / Sitemap ----------

    def _robots_und_sitemap(self) -> None:
        teile = urlsplit(self.e.start_url)
        wurzel = f"{teile.scheme}://{teile.netloc}"
        status, text, sitemaps = None, None, []
        try:
            r = self.client.get(wurzel + "/robots.txt", follow_redirects=True)
            status = r.status_code
            if r.status_code == 200:
                text = r.text.removeprefix("\ufeff")   # BOM (Windows-Editoren): Google ignoriert ihn
                self.robots = RobotsTxt()
                self.robots.parse(text.splitlines())
                sitemaps = self.robots.site_maps() or []
        except httpx.HTTPError:
            pass

        sm = sitemap.laden(self.client, sitemaps or [wurzel + "/sitemap.xml"])
        sitemap_status = sm.dateien[0].status if sm.dateien else None
        self.conn.executemany(
            "INSERT INTO sitemap_dateien (crawl_id, url, status, bytes, url_anzahl, ist_index, fehler)"
            " VALUES (?,?,?,?,?,?,?)",
            [(self.crawl_id, d.url, d.status, d.bytes, d.url_anzahl, int(d.ist_index), d.fehler) for d in sm.dateien])
        self.conn.executemany(
            "INSERT INTO sitemap_eintraege (crawl_id, url, sitemap_url) VALUES (?,?,?)",
            [(self.crawl_id, url, quelle) for url, quelle in sm.eintraege])
        self.sitemap_urls = list(dict.fromkeys(u for u, _ in sm.eintraege if ist_intern(u, self.start_host)))
        self.conn.commit()  # vor weiteren Netzwerkanfragen: keine offene Transaktion

        fakten = site.sammeln(self.client, self.e.start_url)
        self.conn.execute(
            "UPDATE crawls SET robots_status=?, robots_text=?, sitemap_urls=?, sitemap_status=?, fakten=? WHERE id=?",
            (status, text, "\n".join(sitemaps) or None, sitemap_status, json.dumps(fakten), self.crawl_id),
        )
        self.conn.commit()

    def _erlaubt(self, url: str) -> bool:
        if not self.e.robots_beachten:
            return True
        return self.robots.can_fetch(self.e.user_agent, url)

    # ---------- Seiten ----------

    def _seiten_crawlen(self) -> None:
        start = normalisieren(self.e.start_url, self.e.start_url)
        links_folgen = self.e.quelle != "sitemap"
        if links_folgen:
            schlange = deque([(start, 0)])
        else:
            schlange = deque((u, 0) for u in dict.fromkeys(self.filter.bereinigen(u) for u in self.sitemap_urls)
                             if self.filter.erlaubt(u))
        gesehen = {u for u, _ in schlange}
        anzahl = 0
        sitemap_nachgeladen = self.e.quelle != "beides"

        while anzahl < self.e.seitenlimit:
            if not schlange and not sitemap_nachgeladen:
                # Links ausgeschöpft: verwaiste Sitemap-URLs anhängen (Tiefe 0 wie im Sitemap-Modus)
                sitemap_nachgeladen = True
                for u in dict.fromkeys(self.filter.bereinigen(u) for u in self.sitemap_urls):
                    if u not in gesehen and self.filter.erlaubt(u):
                        gesehen.add(u)
                        schlange.append((u, 0))
            if not schlange:
                break
            if self._abbruch_gewuenscht():
                return
            url, tiefe = schlange.popleft()
            anzahl += 1

            if self._erlaubt(url):
                for ziel, ziel_tiefe in self._seite_abrufen(url, tiefe):
                    if (links_folgen and ziel not in gesehen and ist_intern(ziel, self.start_host)
                            and self.filter.erlaubt(ziel)):
                        gesehen.add(ziel)
                        schlange.append((ziel, ziel_tiefe))
                abgerufen = True
            else:
                self._seite_speichern(url, tiefe, blockiert=1)
                abgerufen = False

            # Nach jeder Seite committen: hält Transaktionen kurz, damit UI/MCP nicht blockiert werden
            self._fortschritt(seiten_anzahl=anzahl)
            if schlange and abgerufen:
                self._warten()

    def _seite_abrufen(self, url: str, tiefe: int) -> list[tuple[str, int]]:
        """Ruft eine Seite ab, speichert sie und gibt neu gefundene Ziele zurück."""
        t0 = time.perf_counter()

        def abruf():
            nonlocal t0
            t0 = time.perf_counter()   # Ladezeit nur des letzten Versuchs, Timeouts davor zählen nicht mit
            return _abrufen(self.client, url)

        try:
            r, inhalt, groesse = _mit_wiederholung(abruf)
        except httpx.HTTPError as fehler:
            self._seite_speichern(url, tiefe, abruf_fehler=f"{type(fehler).__name__}: {fehler}"[:300],
                                  ladezeit_ms=int((time.perf_counter() - t0) * 1000))
            return []
        ladezeit = int((time.perf_counter() - t0) * 1000)

        h = r.headers
        daten = dict(
            status_code=r.status_code,
            content_type=h.get("content-type"),
            content_encoding=h.get("content-encoding"),
            x_robots_tag=h.get("x-robots-tag"),
            last_modified=h.get("last-modified"),
            hat_hsts=int("strict-transport-security" in h),
            ladezeit_ms=ladezeit,
            html_bytes=groesse,
        )

        if r.is_redirect and "location" in h:
            ziel = normalisieren(h["location"], url)
            self._seite_speichern(url, tiefe, redirect_ziel=ziel, **daten)
            return [(ziel, tiefe)] if ziel else []

        if r.status_code != 200 or "html" not in (daten["content_type"] or "").lower():
            self._seite_speichern(url, tiefe, **daten)
            return []

        html, woerter_roh = dekodieren(inhalt, daten["content_type"]), None
        if self.renderer:
            gerendert = self.renderer.rendern(url)
            if gerendert:  # Wörter ohne JavaScript merken: zeigt, was Crawler ohne Rendering sehen
                woerter_roh, html = zerlegen(html, url).woerter, gerendert
        inhalt = zerlegen(html, url)
        for l in inhalt.links:  # ignorierte Parameter: Link zählt für die Seite ohne diese Parameter
            if l.art == "a" and ist_intern(l.url, self.start_host):
                l.url = self.filter.bereinigen(l.url)
        seite_id = self._seite_speichern(
            url, tiefe, **daten,
            title=inhalt.title,
            meta_description=inhalt.meta_description,
            h1_anzahl=len(inhalt.h1),
            h1_text=inhalt.h1[0] if inhalt.h1 else None,
            canonical_anzahl=len(inhalt.canonicals),
            canonical=inhalt.canonicals[0] if inhalt.canonicals else None,
            meta_robots=inhalt.meta_robots,
            woerter=inhalt.woerter,
            woerter_roh=woerter_roh,
            js_app=inhalt.js_app,
            text_anteil=inhalt.text_anteil,
            hat_viewport=int(inhalt.hat_viewport),
            viewport_ok=int(inhalt.viewport_ok),
            hat_doctype=int(inhalt.hat_doctype),
            hat_charset=int(inhalt.hat_charset or "charset=" in (daten["content_type"] or "").lower()),
            hat_meta_refresh=int(inhalt.hat_meta_refresh),
            lang=inhalt.lang,
            hat_frames=int(inhalt.hat_frames),
            hat_passwort=int(inhalt.hat_passwort),
            hreflang=json.dumps(inhalt.hreflang),
            markup=json.dumps(inhalt.markup),
            signatur=json.dumps(inhalt.signatur) if inhalt.signatur else None,
            plugins=json.dumps(inhalt.plugins),
            semantik=json.dumps(inhalt.semantik),
            lesbarkeit=json.dumps(inhalt.lesbarkeit),
            kaputte_links=json.dumps(inhalt.kaputte_links),
            geo=json.dumps(inhalt.geo),
            blockierend=json.dumps(inhalt.blockierend),
        )
        self.conn.executemany(
            "INSERT INTO links (crawl_id, seite_id, ziel_url, art, intern, anker_text, nofollow, alt)"
            " VALUES (?,?,?,?,?,?,?,?)",
            [
                (self.crawl_id, seite_id, l.url, l.art, int(ist_intern(l.url, self.start_host)),
                 l.anker_text, int(l.nofollow), l.alt)
                for l in inhalt.links
            ],
        )
        return [(l.url, tiefe + 1) for l in inhalt.links if l.art == "a"]

    def _seite_speichern(self, url: str, tiefe: int, **felder) -> int:
        spalten = ["crawl_id", "url", "tiefe", *felder]
        werte = [self.crawl_id, url, tiefe, *felder.values()]
        cur = self.conn.execute(
            f"INSERT INTO seiten ({', '.join(spalten)}) VALUES ({', '.join('?' * len(werte))})", werte
        )
        return cur.lastrowid

    # ---------- Ressourcen ----------

    def _ressourcen_pruefen(self) -> None:
        """Interne Bilder per HEAD prüfen; interne JS/CSS per GET laden (Größe, Kompression, Caching, Minify)."""
        zeilen = self.conn.execute(
            "SELECT DISTINCT ziel_url, art FROM links WHERE crawl_id=? AND intern=1 AND art != 'a' LIMIT ?",
            (self.crawl_id, MAX_RESSOURCEN),
        ).fetchall()
        for url, art in zeilen:
            if self._abbruch_gewuenscht():
                return
            werte = {"status_code": None}
            try:
                if art in ("script", "css"):
                    werte.update(_datei_laden(self.client, url))
                else:
                    werte["status_code"] = _status(self.client, url)
            except httpx.HTTPError:
                pass
            self._ressource_speichern(url, art, extern=0, **werte)
            self._fortschritt()
            self._warten()

    def _extern_pruefen(self) -> None:
        """Externe Links, Bilder, JS und CSS: nur erreichbar oder nicht (Weiterleitungen werden verfolgt)."""
        zeilen = self.conn.execute(
            "SELECT DISTINCT ziel_url, art FROM links WHERE crawl_id=? AND intern=0 LIMIT ?",
            (self.crawl_id, MAX_EXTERN),
        ).fetchall()
        for url, art in zeilen:
            if self._abbruch_gewuenscht():
                return
            if ist_lokal(url):   # z. B. Knopf „Programm öffnen“ auf localhost: Absicht, nicht prüfbar
                continue
            status = None
            try:
                status = _mit_wiederholung(lambda: _extern_status(self.client, url))
            except httpx.HTTPError:
                pass
            self._ressource_speichern(url, art, extern=1, status_code=status)
            self._fortschritt()
            time.sleep(EXTERN_PAUSE)

    def _ressource_speichern(self, url: str, art: str, **werte) -> None:
        werte = {"crawl_id": self.crawl_id, "url": url, "art": art, **werte}
        self.conn.execute(
            f"INSERT OR REPLACE INTO ressourcen ({', '.join(werte)}) VALUES ({', '.join('?' * len(werte))})",
            tuple(werte.values()),
        )

    # ---------- Sitemap-URLs außerhalb des Crawls ----------

    def _sitemap_urls_pruefen(self) -> None:
        """Status von Sitemap-URLs holen, die der Crawl nicht erreicht hat (für 'falsche Seiten in Sitemap')."""
        gecrawlt = {z[0] for z in self.conn.execute("SELECT url FROM seiten WHERE crawl_id=?", (self.crawl_id,))}
        offen = [u for u in self.sitemap_urls if u not in gecrawlt][:MAX_SITEMAP_PRUEFUNG]
        for url in offen:
            if self._abbruch_gewuenscht():
                return
            status = None
            try:
                r = self.client.head(url)
                if r.status_code in (405, 501):
                    r = self.client.get(url)
                status = r.status_code
            except httpx.HTTPError:
                pass
            self.conn.execute("UPDATE sitemap_eintraege SET status_code=? WHERE crawl_id=? AND url=?",
                              (status, self.crawl_id, url))
            self._fortschritt()
            self._warten()


def _mit_wiederholung(aufruf):
    """Führt aufruf() aus; bei Connect- oder Read-Timeout bis zu WIEDERHOLUNGEN weitere Versuche mit Pause."""
    for versuch in range(WIEDERHOLUNGEN + 1):
        try:
            return aufruf()
        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            if versuch == WIEDERHOLUNGEN:
                raise
            time.sleep(WIEDERHOLEN_PAUSE)


def _abrufen(client: httpx.Client, url: str) -> tuple[httpx.Response, bytes, int | None]:
    """GET als Stream: nur HTML-Seiten mit Status 200 werden gelesen, und das höchstens bis MAX_HTML_BYTES.
    PDFs, Videos und Fehlerseiten kosten so keine Zeit und keinen Speicher. Liefert (Antwort, Inhalt, Größe)."""
    with client.stream("GET", url) as r:
        laenge = r.headers.get("content-length")
        groesse = int(laenge) if laenge and laenge.isdigit() else None
        if r.status_code != 200 or "html" not in (r.headers.get("content-type") or "").lower():
            return r, b"", groesse
        teile, gelesen = [], 0
        for stueck in r.iter_bytes():
            teile.append(stueck)
            gelesen += len(stueck)
            if gelesen > MAX_HTML_BYTES:
                break
        inhalt = b"".join(teile)[:MAX_HTML_BYTES]
        return r, inhalt, max(gelesen, groesse or 0)


def _status(client: httpx.Client, url: str, folgen: bool = False) -> int:
    """HEAD, bei Ablehnung (manche Server mögen kein HEAD) noch einmal per GET."""
    r = client.head(url, follow_redirects=folgen)
    if r.status_code in (403, 405, 501):
        with client.stream("GET", url, follow_redirects=folgen) as r:
            pass
    return r.status_code


def _extern_status(client: httpx.Client, url: str) -> int:
    """HEAD mit Bot-Kennung; bei Ablehnung einmal per GET mit Browser-Kennung nachprüfen.
    Gemeldet wird nur, was auch für einen normalen Browser fehlschlägt."""
    r = client.head(url, follow_redirects=True)
    if r.status_code in EXTERN_NACHPRUEFEN:
        with client.stream("GET", url, follow_redirects=True, headers={"User-Agent": BROWSER_UA}) as r:
            pass
    return r.status_code


def _datei_laden(client: httpx.Client, url: str) -> dict:
    r = client.get(url)
    werte = {"status_code": r.status_code}
    if r.status_code == 200:
        text = r.text
        werte.update(
            bytes=len(r.content),
            content_encoding=r.headers.get("content-encoding"),
            gecacht=int(ressourcen.wird_gecacht(r.headers.get("cache-control"), r.headers.get("expires"))),
            minifiziert=None if (m := ressourcen.ist_minifiziert(text)) is None else int(m),
        )
    return werte
