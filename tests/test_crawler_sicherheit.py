"""Bösartige Muster und übergroße Antworten bleiben zeitlich und räumlich begrenzt."""

import gzip
import multiprocessing
import time

import httpx
import pytest

from app.crawler import crawler, sitemap, site
from app.crawler.filter import UrlFilter
from app.crawler.robots import RobotsTxt


def _boeses_muster(fertig):
    r = RobotsTxt()
    r.parse(["User-agent: *", "Disallow: /" + "*a" * 20 + "X"])
    start = time.monotonic()
    assert r.can_fetch("bot", "https://example.de/" + "a" * 60)
    assert UrlFilter(sperren=["/" + "*a" * 20 + "X"]).erlaubt("https://example.de/" + "a" * 60)
    fertig.put(time.monotonic() - start)


def test_robots_und_filter_ohne_exponentielle_laufzeit():
    # Eigener Prozess: ein Regressionstest darf die Testsuite nicht einfrieren.
    ctx = multiprocessing.get_context("spawn")
    fertig = ctx.Queue()
    prozess = ctx.Process(target=_boeses_muster, args=(fertig,))
    prozess.start()
    try:
        prozess.join(3)
        assert not prozess.is_alive(), "robots-Muster blockiert den Prozess"
        assert prozess.exitcode == 0
        assert fertig.get(timeout=1) < 0.1
    finally:
        if prozess.is_alive():
            prozess.terminate()
        prozess.join()
        fertig.close()


@pytest.mark.parametrize("maske,pfad,passt", [
    ("/a*b$", "/axb", True), ("/a*b$", "/axbc", False),
    ("/a*b", "/axbc", True), ("/a$", "/a", True),
    ("/a.b", "/axb", False), ("/*a*a$", "/a", False),
    ("/a**b$", "/ab", True),
])
def test_robots_platzhalter_bleiben_korrekt(maske, pfad, passt):
    r = RobotsTxt()
    r.parse(["User-agent: *", "Disallow: " + maske])
    assert r.can_fetch("bot", "https://example.de" + pfad) is not passt


def test_sitemap_gzip_bombe_wird_als_fehler_gemeldet(monkeypatch):
    monkeypatch.setattr(sitemap, "MAX_BYTES", 1000)
    daten = gzip.compress(b"<urlset>" + b" " * 100_000 + b"</urlset>")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=daten)))
    datei = sitemap.laden(client, ["https://example.de/sitemap.gz"]).dateien[0]
    assert datei.fehler and "groß" in datei.fehler


class ZaehlerStrom(httpx.SyncByteStream):
    def __init__(self, daten=None):
        self.gelesen = 0
        self.geschlossen = False
        self.daten = daten

    def __iter__(self):
        for stueck in ([self.daten] if self.daten is not None else [b"x" * 1024] * 20):
            self.gelesen += 1
            yield stueck

    def close(self):
        self.geschlossen = True


@pytest.mark.parametrize("art", ["sitemap", "datei", "llms", "endziel", "onpage"])
def test_alle_abrufwege_brechen_grosse_streams_ab(monkeypatch, art):
    from app.core import onpage
    monkeypatch.setattr(sitemap, "MAX_BYTES", 1500)
    monkeypatch.setattr(crawler, "MAX_HTML_BYTES", 1500)
    monkeypatch.setattr(site, "MAX_BYTES", 1500, raising=False)
    monkeypatch.setattr(onpage, "MAX_HTML_BYTES", 1500, raising=False)
    strom = ZaehlerStrom()
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, headers={"Content-Type": "text/html"}, stream=strom)))
    if art == "sitemap":
        assert sitemap.laden(client, ["https://example.de/sitemap.xml"]).dateien[0].fehler
    elif art == "datei":
        with pytest.raises(httpx.HTTPError):
            crawler._datei_laden(client, "https://example.de/app.js")
    elif art == "llms":
        assert site._llms(client, "https://example.de")["status"] is None
    elif art == "endziel":
        assert "fehler" in site._endziel(client, "https://example.de")
    else:
        monkeypatch.setattr(onpage.httpx, "Client", lambda **kw: client)
        with pytest.raises(onpage.OnpageFehler):
            onpage.abrufen("https://example.de/", "test")
    assert strom.gelesen <= 2
    assert strom.geschlossen


def test_robots_txt_stream_wird_begrenzt(monkeypatch):
    from tests.test_crawler_robust import _crawlen, _html
    monkeypatch.setattr(crawler, "MAX_HTML_BYTES", 1500)
    strom = ZaehlerStrom()
    def antwort(r):
        if r.url.path == "/robots.txt":
            return httpx.Response(200, stream=strom)
        if r.url.path == "/":
            return _html("<title>OK</title>")
        return httpx.Response(404)
    assert _crawlen("https://example.de/", antwort)["https://example.de/"][1] == "OK"
    assert strom.gelesen <= 2 and strom.geschlossen


@pytest.mark.parametrize("kodierung", ["gzip", "deflate"])
def test_http_kompression_wird_beim_entpacken_begrenzt(kodierung):
    import zlib
    from app.crawler.lesen import AntwortZuGross, _lesen
    daten = b"x" * 100_000
    strom = ZaehlerStrom(gzip.compress(daten) if kodierung == "gzip" else zlib.compress(daten))
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, headers={"Content-Encoding": kodierung}, stream=strom)))
    with pytest.raises(AntwortZuGross):
        _lesen(client, "https://example.de/", 1500)
    assert strom.geschlossen


def test_redirect_body_wird_nicht_gelesen():
    from app.crawler.lesen import _lesen
    strom = ZaehlerStrom()
    def antwort(r):
        if r.url.path == "/":
            return httpx.Response(302, headers={"Location": "/ziel"}, stream=strom)
        return httpx.Response(200, text="Größe", headers={"Content-Type": "text/plain; charset=utf-8"})
    client = httpx.Client(transport=httpx.MockTransport(antwort))
    r = _lesen(client, "https://example.de/", 1500)
    assert r.text == "Größe" and str(r.url).endswith("/ziel")
    assert len(r.history) == 1
    assert strom.gelesen == 0 and strom.geschlossen


@pytest.mark.parametrize("daten", [gzip.compress(b"<urlset/>")[:-4], b"\x1f\x8bkaputt"])
def test_defektes_gzip_ergibt_dateifehler(daten):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=daten)))
    datei = sitemap.laden(client, ["https://example.de/sitemap.gz"]).dateien[0]
    assert datei.fehler and datei.fehler.startswith("gzip:")
