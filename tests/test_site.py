"""Site-Fakten: HTTPS-Weiterleitung, www, Zertifikat, robots.txt-Format (ohne echtes Netz)."""

from datetime import datetime, timezone

import httpx

from app.checks.site import robots_felder_pruefen, robots_pruefen
from app.crawler import site


def _client(routen: dict) -> httpx.Client:
    """routen: URL → (status, location|None)."""
    def antwort(request: httpx.Request) -> httpx.Response:
        status, ziel = routen.get(str(request.url), (404, None))
        return httpx.Response(status, headers={"Location": ziel} if ziel else {})
    return httpx.Client(transport=httpx.MockTransport(antwort))


def _ohne_tls(monkeypatch):
    monkeypatch.setattr(site, "tls_pruefen", lambda host, port=443: {"name_ok": True})


def test_alles_sauber(monkeypatch):
    _ohne_tls(monkeypatch)
    f = site.sammeln(_client({
        "https://ex.de/": (200, None),
        "http://ex.de/": (301, "https://ex.de/"),
        "https://www.ex.de/": (301, "https://ex.de/"),
    }), "https://ex.de/")
    assert f["http_zu_https"]["ok"] and f["www"]["ok"]


def test_http_ohne_umleitung_und_www_doppelt(monkeypatch):
    _ohne_tls(monkeypatch)
    f = site.sammeln(_client({
        "https://ex.de/": (200, None),
        "http://ex.de/": (200, None),
        "https://www.ex.de/": (200, None),
    }), "https://ex.de/")
    assert not f["http_zu_https"]["ok"]
    assert not f["www"]["ok"]


def test_www_variante_ohne_dns_ist_ok(monkeypatch):
    _ohne_tls(monkeypatch)

    def antwort(request):
        if request.url.host == "www.ex.de":
            raise httpx.ConnectError("DNS")
        return httpx.Response(200)
    f = site.sammeln(httpx.Client(transport=httpx.MockTransport(antwort)), "https://ex.de/")
    assert f["www"]["ok"]


def test_ip_ohne_www_und_tls():
    f = site.sammeln(_client({}), "http://127.0.0.1:8000/")
    assert set(f) == {"llms"}


def test_zertifikat_bewerten():
    jetzt = datetime(2026, 10, 14, tzinfo=timezone.utc)
    assert site.zertifikat_bewerten("Nov 16 12:00:00 2026 GMT", jetzt)["rest_tage"] == 33
    assert site.zertifikat_bewerten("Jan  1 00:00:00 2026 GMT", jetzt)["abgelaufen"]


def test_robots_pruefen():
    assert robots_pruefen("User-agent: *\nDisallow: /a\n# Kommentar\nSitemap: https://x/s.xml\n") == []
    text = "Disallow: /vorher\nUser-agent: *\nDisalow: /x\nKaputt\nNoindex: /alt/\n"
    fehler = robots_pruefen(text)   # echte Formatfehler: Regel vor User-agent, kein Doppelpunkt
    assert len(fehler) == 2
    assert "Zeile 1" in fehler[0] and "Zeile 4" in fehler[1]
    hinweise = robots_felder_pruefen(text)   # unbekanntes Feld und das von Google ignorierte noindex
    assert len(hinweise) == 2
    assert "Zeile 3" in hinweise[0] and "disalow" in hinweise[0] and "Zeile 5" in hinweise[1] and "2019" in hinweise[1]
