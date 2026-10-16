"""Kleine lokale Website mit absichtlich eingebauten SEO-Fehlern für Crawler- und Check-Tests."""

import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GUT = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
<link rel="stylesheet" href="/stil.css"></head>
<body><h1>{h1}</h1><p>{text}</p>{links}</body></html>"""

def lang_text(saat: str) -> str:
    """250 Wörter, je Saat eigener Text: verschiedene Seiten sind keine Duplikate, gleiche Saat schon."""
    zufall = random.Random(saat)
    return " ".join(f"wort{zufall.randrange(1000)}" for _ in range(250))


def seite(title, h1="Überschrift", desc=None, text=None, links=""):
    return GUT.format(title=title, h1=h1, desc=desc or f"Beschreibung {title}", text=text or lang_text(title), links=links)


ROUTEN = {
    "/robots.txt": (200, "text/plain",
                    "User-agent: *\nDisallow: /privat/\nDisalow: /tippfehler/\n\nUser-agent: OAI-SearchBot\nDisallow: /\n"
                    "\nSitemap: {basis}sitemap.xml\n"),
    "/sitemap.xml": (200, "application/xml", """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>{basis}gut</loc></url><url><loc>{basis}doppelt-1</loc></url><url><loc>{basis}doppelt-1</loc></url>
<url><loc>{basis}kaputt</loc></url><url><loc>{basis}umleitung</loc></url>
<url><loc>{basis}gut?variante=2</loc></url><url><loc>{basis}verwaist</loc></url>
</urlset>"""),
    "/verwaist": (200, "text/html; charset=utf-8", seite("Verwaiste Seite")),
    # Inhalt entsteht erst per JavaScript (nicht verlinkt, nur für den Render-Test)
    "/js": (200, "text/html; charset=utf-8", """<!doctype html><html lang="de"><head><meta charset="utf-8">
<title>JavaScript-Seite</title></head><body><h1>App</h1><div id="app"></div>
<script>document.getElementById('app').innerHTML = '<p>' + Array.from({length: 300}, (_, i) => 'inhalt' + i).join(' ')
  + '</p><a href="/gut">Gute Seite</a>';</script></body></html>"""),
    "/llms.txt": (200, "text/plain", "Kein Markdown-Titel\n- Link\n"),
    "/": (200, "text/html; charset=utf-8", seite(
        "Startseite der Testseite", links="""
        <a href="/gut">Gute Seite</a> <a href="/ohne-title">Ohne Title</a>
        <a href="/doppelt-1">Doppelt 1</a> <a href="/doppelt-2">Doppelt 2</a>
        <a href="/kaputt">Kaputter Link</a> <a href="/serverfehler">Server</a>
        <a href="/umleitung">hier</a> <a href="/privat/geheim">Privat</a>
        <a href="/schlecht">Schlechte Seite</a> <a href="https://extern.example/" rel="nofollow">Extern</a>
        <a href="/gut" rel="nofollow">Gut nofollow</a><a href="/gut"></a>
        <a href="/gut?variante=2">Variante</a> <a href="/gut" aria-label="Gut per Icon"><svg></svg></a>""")),
    "/stil.css": (200, "text/css", "body{}"),
    # Lesbar formatiert, > 2 KB, ohne Kompression und Cache-Header
    "/gross.js": (200, "application/javascript", "function f() {\n    return 1;\n}\n" * 120),
    "/gut": (200, "text/html; charset=utf-8", seite("Eine gute Unterseite", links='<a href="/">Start</a>')),
    "/gut?variante=2": (200, "text/html; charset=utf-8", seite("Eine gute Unterseite").replace(
        "</head>", '<link rel="canonical" href="/gut"></head>')),
    "/ohne-title": (200, "text/html; charset=utf-8", seite("", links='<a href="/">Start</a>')),
    "/doppelt-1": (200, "text/html; charset=utf-8", seite("Gleicher Title", desc="Gleich")),
    "/doppelt-2": (200, "text/html; charset=utf-8", seite("Gleicher Title", desc="Gleich")),
    "/kaputt": (404, "text/html", "<h1>Nicht gefunden</h1>"),
    "/serverfehler": (500, "text/html", "<h1>Fehler</h1>"),
    "/umleitung": (302, None, "/gut"),
    "/privat/geheim": (200, "text/html", seite("Geheim")),
    # Viele Fehler auf einmal: kein doctype/lang/viewport, kurzer Title, zwei H1, wenig Text, Bild ohne alt
    "/schlecht": (200, "text/html", """<html><head><title>Kurz</title>
        <meta http-equiv="refresh" content="5"></head>
        <body><h1>Eins</h1><h1>Zwei</h1><p>Wenig Text.</p>
        <img src="/fehlt.png"><a href="/kaputt">mehr</a><script src="/gross.js"></script></body></html>"""),
}


class Handler(BaseHTTPRequestHandler):
    def _antwort(self, mit_body: bool):
        pfad = self.path if self.path in ROUTEN else self.path.split("?")[0]
        status, typ, inhalt = ROUTEN.get(pfad, (404, "text/html", "<h1>404</h1>"))
        self.send_response(status)
        if 300 <= status < 400:
            self.send_header("Location", inhalt)
            inhalt = ""
        if typ:
            self.send_header("Content-Type", typ)
        basis = f"http://{self.headers.get('Host')}/"
        inhalt = inhalt.replace("{basis}", basis)
        daten = inhalt.encode()
        self.send_header("Content-Length", str(len(daten)))
        self.end_headers()
        if mit_body:
            self.wfile.write(daten)

    def do_GET(self):
        self._antwort(True)

    def do_HEAD(self):
        self._antwort(False)

    def log_message(self, *args):
        pass


def starten() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/"


if __name__ == "__main__":
    # Manuell starten, z. B. zum Ausprobieren in der UI: python -m tests.testseite
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8799
    print(f"Testseite läuft auf http://127.0.0.1:{port}/")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
