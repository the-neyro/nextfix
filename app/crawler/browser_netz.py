"""Lokaler SOCKS5-Proxy für Chromium, damit auch Browser-Abrufe den Netzzielschutz nutzen."""

import select
import socket
from contextlib import contextmanager
from socketserver import StreamRequestHandler, ThreadingTCPServer
from threading import Lock, Thread

from app.crawler.netz import Zielbereich

# Chromiums implizite Ausnahme für Loopback und Link-Local entfernen.
# UDP für QUIC und WebRTC kann der SOCKS-Proxy nicht filtern.
CHROMIUM_ARGS = [
    "--proxy-bypass-list=<-loopback>",
    "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
    "--disable-quic",
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
]


class _Proxy(ThreadingTCPServer):
    daemon_threads = True

    def __init__(self, start_url: str | None):
        self.zielbereich = Zielbereich(start_url)
        self._lock = Lock()
        self._verbindungen = set()
        self._geschlossen = False
        super().__init__(("127.0.0.1", 0), _Socks)

    @contextmanager
    def aktiv(self, verbindung):
        with self._lock:
            if self._geschlossen:
                raise OSError("Proxy geschlossen")
            self._verbindungen.add(verbindung)
        try:
            yield
        finally:
            with self._lock:
                self._verbindungen.discard(verbindung)

    def server_close(self):
        with self._lock:
            self._geschlossen = True
            for verbindung in self._verbindungen:
                try:
                    verbindung.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        super().server_close()


class _Socks(StreamRequestHandler):
    timeout = 15
    rbufsize = 0  # Keine Tunnel-Nutzdaten beim Lesen der Anfrage puffern.
    ERFOLG = b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    ABGELEHNT = b"\x05\x02\x00\x01\x00\x00\x00\x00\x00\x00"

    def _lesen(self, anzahl):
        daten = bytearray()
        while len(daten) < anzahl:
            stueck = self.rfile.read(anzahl - len(daten))
            if not stueck:
                raise EOFError
            daten.extend(stueck)
        return bytes(daten)

    def _ziel(self):
        version, anzahl = self._lesen(2)
        if version != 5 or 0 not in self._lesen(anzahl):
            self.wfile.write(b"\x05\xff")
            raise EOFError
        self.wfile.write(b"\x05\x00")
        version, kommando, reserviert, typ = self._lesen(4)
        if (version, kommando, reserviert) != (5, 1, 0):
            raise ValueError
        if typ == 1:
            host = socket.inet_ntop(socket.AF_INET, self._lesen(4))
        elif typ == 4:
            host = socket.inet_ntop(socket.AF_INET6, self._lesen(16))
        elif typ == 3:
            host = self._lesen(self._lesen(1)[0]).decode("ascii")
            if not host:
                raise ValueError
        else:
            raise ValueError
        return host, int.from_bytes(self._lesen(2), "big")

    def handle(self):
        try:
            with self.server.aktiv(self.connection):
                self._verbinden()
        except OSError:
            pass

    def _verbinden(self):
        try:
            host, port = self._ziel()
            ziel = self.server.zielbereich.verbinden(host, port, self.timeout)
        except EOFError:
            return
        except (OSError, ValueError):
            self.wfile.write(self.ABGELEHNT)
            return
        with ziel, self.server.aktiv(ziel):
            self.wfile.write(self.ERFOLG)
            gegenstellen = {self.connection: ziel, ziel: self.connection}
            while gegenstellen:
                lesbar, _, _ = select.select(list(gegenstellen), [], [], 60)
                if not lesbar:
                    break
                for quelle in lesbar:
                    daten = quelle.recv(64 * 1024)
                    if daten:
                        gegenstellen[quelle].sendall(daten)
                    else:
                        gegenstellen.pop(quelle).shutdown(socket.SHUT_WR)


@contextmanager
def proxy(start_url: str | None):
    with _Proxy(start_url) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join()


@contextmanager
def browser(start_url: str | None):
    from playwright.sync_api import sync_playwright

    with proxy(start_url) as server, sync_playwright() as pw:
        chromium = pw.chromium.launch(
            proxy={"server": f"socks5://127.0.0.1:{server.server_address[1]}"},
            args=CHROMIUM_ARGS,
        )
        try:
            yield chromium, server
        finally:
            chromium.close()
