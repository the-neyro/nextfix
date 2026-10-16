"""Demo-Website „Radhaus Elbe“ (erfundene Fahrradwerkstatt in Hamburg) für Screenshots und zum Ausprobieren.

Bewusst mit typischen Schwächen kleiner Firmen-Websites: dünne Seiten, zu lange Titles, doppelte Beschreibungen,
Artikel ohne Datum, Bilder ohne Alt-Text, ein toter Link, eine Weiterleitung, keine llms.txt.
Alle Namen, Adressen und Zahlen sind erfunden.

Start: .venv/bin/python -m scripts.demo_website 8798
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MENUE = [("/", "Start"), ("/werkstatt", "Werkstatt"), ("/e-bikes", "E-Bikes"), ("/leihraeder", "Leihräder"),
         ("/preise", "Preise"), ("/blog", "Ratgeber"), ("/faq", "FAQ"), ("/kontakt", "Kontakt")]

ORGANISATION = """<script type="application/ld+json">{"@context":"https://schema.org","@type":"LocalBusiness",
"name":"Radhaus Elbe","url":"{basis}","telephone":"+49 40 000000","address":{"@type":"PostalAddress",
"streetAddress":"Musterstraße 1","postalCode":"20000","addressLocality":"Hamburg"}}</script>"""


def _seite(title: str, h1: str, inhalt: str, desc: str | None = None, kopf: str = "") -> str:
    menue = "".join(f'<a href="{p}">{n}</a> ' for p, n in MENUE)
    meta = f'<meta name="description" content="{desc}">' if desc else ""
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>{meta}{kopf}
<link rel="stylesheet" href="/stil.css"></head><body>
<header><a href="/"><img src="/logo.png" alt="Radhaus Elbe"></a><nav>{menue}</nav></header>
<main><h1>{h1}</h1>{inhalt}</main>
<footer><a href="/impressum">Impressum</a> <a href="/datenschutz">Datenschutz</a> · Radhaus Elbe, Hamburg</footer>
</body></html>"""


def _absaetze(*texte: str, mal: int = 1) -> str:
    return "".join(f"<p>{t}</p>" for _ in range(mal) for t in texte)


WERKSTATT = _absaetze(
    "In unserer Werkstatt in Hamburg-Altona reparieren wir Citybikes, Rennräder, Lastenräder und E-Bikes aller "
    "gängigen Hersteller. Die meisten Reparaturen erledigen wir am selben Tag, wenn du dein Rad bis 10 Uhr bringst.",
    "Zur Inspektion gehören Bremsen, Schaltung, Kette, Laufräder, Licht und ein kurzer Sicherheitscheck. Danach "
    "bekommst du ein Protokoll mit allem, was wir geprüft und eingestellt haben.",
    "Ersatzteile verbauen wir nur nach Absprache. Du bekommst vorher einen Kostenvoranschlag, und wir rufen an, "
    "wenn während der Reparatur etwas Unerwartetes auftaucht.", mal=3)

SEITEN: dict[str, tuple[int, str]] = {
    "/": (200, _seite("Radhaus Elbe – Fahrradwerkstatt in Hamburg-Altona", "Deine Fahrradwerkstatt in Altona",
        _absaetze("Reparatur, Inspektion und E-Bike-Service mitten in Hamburg. Seit 2014 halten wir die Räder "
                  "unserer Nachbarschaft am Laufen – schnell, ehrlich und zu festen Preisen.",
                  "Termin brauchst du nur für die große Inspektion. Kleine Reparaturen wie Schlauchwechsel oder "
                  "Bremsen einstellen machen wir meist sofort, während du einen Kaffee trinkst.", mal=5)
        + '<h2>Unsere Leistungen</h2><ul><li><a href="/werkstatt">Reparatur und Inspektion</a></li>'
          '<li><a href="/e-bikes">E-Bike-Service</a></li><li><a href="/leihraeder">Leihräder</a></li></ul>'
          '<img src="/werkstatt.jpg"><img src="/team.jpg">',
        "Fahrradwerkstatt in Hamburg-Altona: Reparatur, Inspektion und E-Bike-Service zu festen Preisen. "
        "Kleine Reparaturen oft sofort.", ORGANISATION)),
    "/werkstatt": (200, _seite("Fahrradreparatur und Inspektion in Hamburg | Radhaus Elbe",
        "Reparatur und Inspektion", WERKSTATT + "<h2>Was kostet die Inspektion?</h2><p>Die Standard-Inspektion "
        "kostet 69 €, für E-Bikes 89 €. Teile kommen extra dazu.</p><h2>Wie lange dauert eine Reparatur?</h2>"
        "<p>Meist am selben Tag, bei Teilebestellung zwei bis drei Werktage.</p>",
        "Fahrradreparatur und Inspektion in Hamburg-Altona: Bremsen, Schaltung, Kette und Laufräder. "
        "Kostenvoranschlag vorab, oft am selben Tag fertig.")),
    "/e-bikes": (200, _seite("E-Bike-Service Hamburg: Inspektion, Akku-Check, Motor | Radhaus Elbe",
        "E-Bike-Service", _absaetze(
            "Wir warten E-Bikes mit Motoren von Bosch, Shimano und Brose. Zum Service gehören Software-Update, "
            "Akku-Diagnose und ein Test der Bremsen, die bei E-Bikes deutlich stärker beansprucht werden.",
            "Ein Akku verliert pro Jahr etwa 5 bis 10 Prozent seiner Kapazität. Bei der Diagnose siehst du, "
            "wie viel Reichweite dir noch bleibt und ob sich ein Tausch lohnt.", mal=5) + '<img src="/ebike.jpg">',
        "E-Bike-Service in Hamburg: Inspektion, Akku-Diagnose und Software-Update für Bosch, Shimano und Brose.")),
    "/leihraeder": (200, _seite("Leihräder in Hamburg-Altona mieten – Citybikes, E-Bikes und Lastenräder für "
        "einen Tag oder eine Woche | Radhaus Elbe", "Leihräder", _absaetze(
            "Während deiner Reparatur bekommst du auf Wunsch ein Leihrad. Wir verleihen auch an Gäste: Citybikes "
            "ab 15 € am Tag, E-Bikes ab 35 € und Lastenräder ab 45 €.", mal=8),
        "Leihräder in Hamburg-Altona: Citybikes, E-Bikes und Lastenräder ab 15 € pro Tag.")),
    "/preise": (200, _seite("Preise | Radhaus Elbe", "Preise",
        "<p>Feste Preise für die häufigsten Arbeiten.</p><table><tr><td>Schlauch wechseln</td><td>15 €</td></tr>"
        "<tr><td>Bremsen einstellen</td><td>12 €</td></tr><tr><td>Inspektion</td><td>69 €</td></tr>"
        "<tr><td>Inspektion E-Bike</td><td>89 €</td></tr></table>",
        "Unsere Preise für Reparatur und Inspektion.")),
    "/ueber-uns": (200, _seite("Über uns | Radhaus Elbe", "Über uns",
        "<p>Wir sind drei Mechaniker aus Altona und lieben Fahrräder.</p><img src='/team.jpg'>",
        "Unsere Preise für Reparatur und Inspektion.")),
    "/kontakt": (200, _seite("Kontakt | Radhaus Elbe", "Kontakt",
        "<p>Musterstraße 1, 20000 Hamburg. Montag bis Freitag 9–18 Uhr, Samstag 10–14 Uhr.</p>")),
    "/blog": (200, _seite("Ratgeber | Radhaus Elbe", "Ratgeber",
        '<ul><li><a href="/blog/kette-oelen">Kette richtig ölen</a></li>'
        '<li><a href="/blog/reifendruck">Der richtige Reifendruck</a></li>'
        '<li><a href="/blog/winter-check">Fahrrad winterfest machen</a></li></ul>',
        "Tipps rund ums Fahrrad aus unserer Werkstatt.")),
    "/blog/kette-oelen": (200, _seite("Fahrradkette richtig ölen: Anleitung in 5 Schritten | Radhaus Elbe",
        "Fahrradkette richtig ölen", _absaetze(
            "Eine gepflegte Kette schaltet sauberer und hält länger. Wir empfehlen, sie etwa alle 300 Kilometer "
            "oder nach jeder Regenfahrt zu reinigen und neu zu ölen.",
            "Zuerst groben Schmutz mit einem Lappen abwischen, dann sparsam Kettenöl auf jedes Glied geben, kurz "
            "einwirken lassen und überschüssiges Öl wieder abwischen.", mal=5)
        + "<h2>Welches Öl ist das richtige?</h2><p>Für nasses Wetter Nassöl, sonst Trockenschmierstoff.</p>"
          "<h2>Wie oft sollte man die Kette ölen?</h2><p>Etwa alle 300 Kilometer.</p>",
        "Fahrradkette ölen: So geht es richtig, wie oft und mit welchem Öl.",
        '<meta property="og:type" content="article"><script type="application/ld+json">{"@context":"https://schema.org",'
        '"@type":"BlogPosting","headline":"Fahrradkette richtig ölen","datePublished":"2026-03-02",'
        '"author":{"@type":"Person","name":"Jonas"}}</script>')),
    "/blog/reifendruck": (200, _seite("Der richtige Reifendruck beim Fahrrad: Tabelle für Citybike, Rennrad, "
        "Mountainbike und E-Bike mit allen Werten in bar und PSI | Radhaus Elbe", "Der richtige Reifendruck",
        _absaetze("Zu wenig Luft macht das Fahren schwer und führt zu Platten, zu viel Luft macht das Rad unruhig. "
                  "Der passende Druck steht als Spanne auf der Reifenflanke.",
                  "Als Faustregel gilt: Citybike 3,5 bis 5 bar, Rennrad 6 bis 8 bar, Mountainbike 1,8 bis 2,5 bar. "
                  "Schwere Fahrer und E-Bikes eher am oberen Ende.", mal=5),
        "Reifendruck beim Fahrrad: Werte für Citybike, Rennrad, Mountainbike und E-Bike.",
        '<meta property="og:type" content="article">')),
    "/blog/winter-check": (200, _seite("Fahrrad winterfest machen | Radhaus Elbe", "Fahrrad winterfest machen",
        _absaetze("Im Winter setzen Salz und Nässe dem Rad zu. Licht prüfen, Kette öfter pflegen und Reifen mit "
                  "etwas weniger Druck fahren – dann kommst du sicher durch die dunkle Jahreszeit.", mal=2),
        "Tipps rund ums Fahrrad aus unserer Werkstatt.")),
    "/faq": (200, _seite("Häufige Fragen | Radhaus Elbe", "Häufige Fragen",
        "<h2>Brauche ich einen Termin?</h2><p>Nur für die große Inspektion.</p>"
        "<h2>Kann ich mit Karte zahlen?</h2><p>Ja, mit EC- und Kreditkarte.</p>"
        "<h2>Reparieren Sie auch Lastenräder?</h2><p>Ja, alle gängigen Modelle.</p>",
        "Antworten auf häufige Fragen zu Termin, Zahlung und Reparatur.")),
    "/angebote": (200, _seite("Angebote | Radhaus Elbe", "Angebote",
        '<p>Aktuell: 10 % auf alle Inspektionen im März. <a href="/fruehjahrsaktion-2025">Zur alten Aktion</a></p>',
        "Aktuelle Angebote der Fahrradwerkstatt.")),
    "/fahrradleasing": (301, "/e-bikes"),
    "/impressum": (200, _seite("Impressum | Radhaus Elbe", "Impressum",
        "<p>Radhaus Elbe GmbH (erfunden), Musterstraße 1, 20000 Hamburg.</p>", "Impressum")),
    "/datenschutz": (200, _seite("Datenschutz | Radhaus Elbe", "Datenschutz",
        _absaetze("Wir verarbeiten deine Daten nur, um Reparaturaufträge abzuwickeln.", mal=2), "Datenschutz")),
}
DATEIEN = {
    "/robots.txt": ("text/plain", "User-agent: *\nAllow: /\n\nSitemap: {basis}sitemap.xml\n"),
    "/sitemap.xml": ("application/xml", '<?xml version="1.0" encoding="UTF-8"?>'
                     '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                     + "".join(f"<url><loc>{{basis}}{p.lstrip('/')}</loc></url>" for p in SEITEN if SEITEN[p][0] == 200)
                     + "<url><loc>{basis}fahrradleasing</loc></url></urlset>"),
    "/stil.css": ("text/css", "body{font-family:sans-serif;max-width:60rem;margin:auto}nav a{margin-right:1rem}"),
}


class Handler(BaseHTTPRequestHandler):
    def _antwort(self, mit_body: bool):
        pfad = self.path.split("?")[0]
        basis = f"http://{self.headers.get('Host')}/"
        if pfad in SEITEN:
            status, inhalt = SEITEN[pfad]
            typ = "text/html; charset=utf-8"
        elif pfad in DATEIEN:
            status, (typ, inhalt) = 200, DATEIEN[pfad]
        elif pfad.endswith((".jpg", ".png")):
            status, typ, inhalt = 200, "image/png", ""
        else:
            status, typ, inhalt = 404, "text/html; charset=utf-8", "<h1>Seite nicht gefunden</h1>"
        self.send_response(status)
        if 300 <= status < 400:
            self.send_header("Location", inhalt)
            inhalt = ""
        daten = inhalt.replace("{basis}", basis).encode()
        self.send_header("Content-Type", typ)
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


def starten(port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/"


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8798
    print(f"Radhaus Elbe (Demo) läuft auf http://127.0.0.1:{port}/")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
