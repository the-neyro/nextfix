"""Synthetische Netzziele, ohne ausgehende Anfragen an öffentliche Server."""

import socket
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from threading import Thread

import httpcore
import pytest

from app.core import audit, onpage, projekte
from app.crawler import browser_netz, netz, rendern, vitals
from app.db import verbinden

OEFFENTLICHE_IP = "93.184.216.34"


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "::ffff:127.0.0.1", "::ffff:169.254.169.254",
                                  "224.0.0.1", "ff02::1", "10.0.0.1", "169.254.169.254", "2002:7f00:1::"])
def test_oeffentliche_pruefung_sperrt_lokale_und_spezielle_adressen(host):
    with pytest.raises(OSError, match="Nicht öffentlich"):
        netz.Zielbereich().adressen(host, 80)


def test_lokales_ziel_muss_ausdruecklich_und_portgenau_gewaehlt_sein(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 8080))])
    assert netz.Zielbereich("http://localhost:8080/").adressen("localhost", 8080) == ["127.0.0.1"]
    assert netz.Zielbereich("http://[::1]:8080/").adressen("::1", 8080) == ["::1"]
    with pytest.raises(OSError, match="Nicht öffentlich"):
        netz.Zielbereich("http://localhost:8080/").adressen("localhost", 8081)
    with pytest.raises(OSError, match="Nicht öffentlich"):
        netz.Zielbereich("http://example.test:8080/").adressen("example.test", 8080)


def test_http_backend_verbindet_nur_die_gepruefte_adresse(monkeypatch):
    aufloesungen, verbindungen = [], []

    def dns(host, port, **_):
        aufloesungen.append(host)
        ip = OEFFENTLICHE_IP if len(aufloesungen) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    def verbinden(_backend, host, port, *_):
        verbindungen.append((host, port))

    monkeypatch.setattr(socket, "getaddrinfo", dns)
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", verbinden)
    backend = netz._Backend(netz.Zielbereich("https://public.example/"))
    backend.connect_tcp("public.example", 443)
    with pytest.raises(httpcore.ConnectError, match="Nicht öffentlich"):
        backend.connect_tcp("public.example", 443)
    assert aufloesungen == ["public.example"] * 2
    assert verbindungen == [(OEFFENTLICHE_IP, 443)]


def test_socks_anfrage_kann_in_einzelnen_bytes_ankommen():
    class InTeilen:
        def __init__(self):
            self.daten = iter(bytes((byte,)) for byte in b"\x05\x01\x00\x05\x01\x00\x01\x7f\x00\x00\x01\x00\x50")

        def read(self, _anzahl):
            return next(self.daten, b"")

    handler = object.__new__(browser_netz._Socks)
    handler.rfile = InTeilen()
    handler.wfile = BytesIO()
    assert handler._ziel() == ("127.0.0.1", 80)
    assert handler.wfile.getvalue() == b"\x05\x00"


def test_proxy_schliesst_aktive_verbindungen_bei_ende():
    with ExitStack() as verbindungen:
        with browser_netz.proxy(None) as server:
            client = verbindungen.enter_context(socket.create_connection(server.server_address, timeout=2))
            client.sendall(b"\x05\x01\x00")
            with client.makefile("rb") as antwort:
                assert antwort.read(2) == b"\x05\x00"
        assert client.recv(1) == b""


@pytest.fixture
def webziele(monkeypatch):
    abrufe = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            host = self.headers["Host"]
            abrufe.append((host, self.path))
            lokal = f"http://127.0.0.1:{self.server.server_port}"
            cdn = f"http://cdn.example:{self.server.server_port}"
            dateien = {
                "/robots.txt": f"Sitemap: {cdn}/sitemap.xml",
                "/sitemap.xml": (f"<sitemapindex><sitemap><loc>{lokal}/privat.xml</loc></sitemap>"
                                 f"<sitemap><loc>{cdn}/umleitung</loc></sitemap></sitemapindex>"),
                "/llms.txt": "",
                "/": (f'<html><title>Test</title><body><script src="{cdn}/script.js"></script>'
                      f'<script src="{lokal}/privat.js"></script></body></html>'),
                "/script.js": "document.body.append('Öffentliches Skript');",
                "/privat.js": "document.body.append('Privates Skript');",
            }
            if self.path in ("/umleitung", "/llms.txt"):
                self.send_response(302)
                self.send_header("Location", f"{lokal}/privat")
                self.end_headers()
                return
            self.send_response(200)
            if self.path == "/":
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(dateien.get(self.path, "").encode())

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        getaddrinfo = socket.getaddrinfo
        create_connection = socket.create_connection

        def dns(host, port, *args, **kwargs):
            if host in {"public.example", "www.public.example", "cdn.example"}:
                host = OEFFENTLICHE_IP
            return getaddrinfo(host, port, *args, **kwargs)

        def verbinden(ziel, *args, **kwargs):
            host, port = ziel
            if host == OEFFENTLICHE_IP:
                host = "127.0.0.1"  # Nur die synthetische öffentliche IP landet auf dem Testserver.
            return create_connection((host, port), *args, **kwargs)

        monkeypatch.setattr(socket, "getaddrinfo", dns)
        monkeypatch.setattr(socket, "create_connection", verbinden)
        try:
            yield f"http://public.example:{server.server_port}/", abrufe
        finally:
            server.shutdown()
            thread.join()


def test_crawl_und_onpage_sperren_sitemap_und_redirect_auf_lokale_ziele(webziele):
    url, abrufe = webziele
    conn = verbinden()
    projekt = projekte.anlegen(conn, "public.example")
    audit.einstellungen_setzen(conn, projekt.id, start_url=url, crawl_delay=0)
    crawl = audit.crawl_starten(conn, projekt.id, warten=True)
    assert crawl["status"] == "fertig", crawl["fehler_text"]
    assert {pfad for _, pfad in abrufe} >= {"/robots.txt", "/sitemap.xml", "/umleitung", "/llms.txt", "/"}
    assert not any(pfad.startswith("/privat") for _, pfad in abrufe)
    assert onpage.abrufen(url, "test")[0] == 200
    with pytest.raises(onpage.OnpageFehler, match="ConnectError"):
        onpage.abrufen(url + "umleitung", "test")
    lokal = url.replace("public.example", "127.0.0.1")
    assert onpage.abrufen(lokal, "test")[0] == 200  # ausdrücklich als Hauptziel gewählt
    ergebnis = onpage.pruefen(conn, projekt.id, url, "test", [lokal + "privat"], mit_suggest=False)
    assert "ConnectError" in ergebnis["mitbewerber"][0]["fehler"]
    assert not any(pfad.startswith("/privat") for _, pfad in abrufe)


def test_chromium_laesst_oeffentliche_ressource_durch_und_sperrt_loopback(webziele):
    url, abrufe = webziele
    playwright = pytest.importorskip("playwright.sync_api")
    with ExitStack() as cleanup:
        try:
            renderer = cleanup.enter_context(rendern.Renderer("Test", start_url=url, ruhe_ms=50))
        except playwright.Error as fehler:
            if "Executable doesn't exist" in str(fehler):
                pytest.skip("Chromium fehlt")
            raise
        html = renderer.rendern(url)
        assert html is not None, renderer.fehler
        assert "Öffentliches Skript" in html and "Privates Skript" not in html
        assert renderer.rendern(url + "umleitung") is None
        proxy_adresse = renderer._proxy.server_address
    with pytest.raises(OSError):
        socket.create_connection(proxy_adresse, timeout=1)
    with vitals.Messer(drosseln=False, nachlauf_ms=0, start_url=url) as messer:
        ergebnis = messer.messen(url + "umleitung")
        assert ergebnis.fehler
    assert not any(pfad.startswith("/privat") for _, pfad in abrufe)
