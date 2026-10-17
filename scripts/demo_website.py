"""Demo-Website „Radhaus Elbe“ (erfundene Fahrradwerkstatt in Hamburg) für Screenshots und zum Ausprobieren.

Bewusst mit typischen Schwächen kleiner Firmen-Websites: dünne Seiten, zu lange Titles, doppelte Beschreibungen,
Artikel ohne Datum, Bilder ohne Alt-Text, ein toter Link, eine Weiterleitung, keine llms.txt.
Alle Namen, Adressen und Zahlen sind erfunden.

Start: .venv/bin/python -m scripts.demo_website 8798            (Variante mit behobenen Aufgaben: --nachher)
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


# Variante „nachher“: die ersten vier Aufgaben aus „Was jetzt tun“ sind behoben (scripts/vorher_nachher.py).
# Dünne Seiten ausgebaut, Rechtsseiten auf noindex, eigene Beschreibungen, Sitemap ohne Weiterleitung, toter Link weg.
# Bildbeschreibungen, zu lange Titles und die fehlende Beschreibung der Kontaktseite bleiben absichtlich offen.
NOINDEX = '<meta name="robots" content="noindex, follow">'
SEITEN_NACHHER: dict[str, tuple[int, str]] = dict(SEITEN)
SEITEN_NACHHER.update({
    "/preise": (200, _seite("Preise | Radhaus Elbe", "Preise",
        "<p>Feste Preise für die häufigsten Arbeiten.</p><table><tr><td>Schlauch wechseln</td><td>15 €</td></tr>"
        "<tr><td>Bremsen einstellen</td><td>12 €</td></tr><tr><td>Inspektion</td><td>69 €</td></tr>"
        "<tr><td>Inspektion E-Bike</td><td>89 €</td></tr></table>" + _absaetze(
            "Alle Preise verstehen sich inklusive Arbeitszeit und Mehrwertsteuer. Ersatzteile wie Schläuche, "
            "Bremsbeläge oder Ketten rechnen wir zum Listenpreis des Herstellers ab und nennen sie dir vorher.",
            "Bei der Inspektion prüfen wir Bremsen, Schaltung, Kette, Laufräder, Licht und Rahmen. Findet sich dabei "
            "etwas, das repariert werden sollte, rufen wir dich an und du entscheidest, ob wir es machen.",
            "Für E-Bikes kommt die Akku-Diagnose und ein Software-Update des Motors dazu. Lastenräder brauchen wegen "
            "Größe und Gewicht etwas mehr Zeit, deshalb kostet ihre Inspektion 99 Euro.", mal=3),
        "Feste Preise der Fahrradwerkstatt in Hamburg-Altona: Schlauch wechseln 15 €, Inspektion 69 €, "
        "E-Bike-Inspektion 89 €. Teile nennen wir dir vorher.")),
    "/ueber-uns": (200, _seite("Über uns | Radhaus Elbe", "Über uns",
        "<img src='/team.jpg'>" + _absaetze(
            "Wir sind drei Mechaniker aus Altona und lieben Fahrräder. Angefangen hat alles 2014 in einer Garage "
            "im Hinterhof, heute haben wir eine Werkstatt mit vier Montageständen und einem kleinen Laden.",
            "Jonas kümmert sich um Rennräder und Laufräder, Mira ist unsere Spezialistin für E-Bikes und Akkus, "
            "und Can repariert alles, was mit Lastenrädern und Kindersitzen zu tun hat.",
            "Uns ist wichtig, dass du verstehst, was an deinem Rad gemacht wird. Deshalb zeigen wir dir alte Teile, "
            "erklären die Reparatur und geben dir Tipps, wie du kleine Dinge künftig selbst erledigst.", mal=3),
        "Das Team von Radhaus Elbe: drei Mechaniker aus Hamburg-Altona, seit 2014 für Rennräder, E-Bikes und "
        "Lastenräder.")),
    "/kontakt": (200, _seite("Kontakt | Radhaus Elbe", "Kontakt",
        "<p>Musterstraße 1, 20000 Hamburg. Montag bis Freitag 9–18 Uhr, Samstag 10–14 Uhr.</p>" + _absaetze(
            "Am schnellsten erreichst du uns telefonisch während der Öffnungszeiten. Für die große Inspektion "
            "vereinbarst du am besten einen Termin, kleine Reparaturen kannst du einfach vorbeibringen.",
            "Mit der S-Bahn bist du in fünf Minuten vom Bahnhof Altona bei uns. Direkt vor der Werkstatt gibt es "
            "Fahrradbügel, und für Lastenräder ist im Hof genug Platz zum Abstellen.",
            "Wenn dein Rad nicht mehr fährt, holen wir es im Umkreis von drei Kilometern für 15 Euro ab und bringen "
            "es nach der Reparatur wieder zurück. Ruf einfach an und sag uns, wo es steht.", mal=3))),
    "/blog": (200, _seite("Ratgeber | Radhaus Elbe", "Ratgeber",
        _absaetze("In unserem Ratgeber schreiben wir auf, was wir in der Werkstatt jeden Tag erklären. Die "
                  "Anleitungen sind für Einsteiger gedacht und brauchen kein Spezialwerkzeug.", mal=2)
        + '<h2><a href="/blog/kette-oelen">Kette richtig ölen</a></h2>' + _absaetze(
            "Eine gepflegte Kette schaltet sauberer und hält länger. Wir zeigen in fünf Schritten, wie du sie "
            "reinigst, welches Öl zu welchem Wetter passt und wie oft du ölen solltest.", mal=2)
        + '<h2><a href="/blog/reifendruck">Der richtige Reifendruck</a></h2>' + _absaetze(
            "Zu wenig Luft macht das Fahren schwer, zu viel macht das Rad unruhig. In der Tabelle findest du "
            "Richtwerte für Citybike, Rennrad, Mountainbike und E-Bike in bar und PSI.", mal=2)
        + '<h2><a href="/blog/winter-check">Fahrrad winterfest machen</a></h2>' + _absaetze(
            "Salz, Nässe und Dunkelheit setzen dem Rad im Winter zu. Unsere Checkliste hilft dir, Licht, Bremsen, "
            "Kette und Reifen vorzubereiten, damit du sicher durch die kalte Jahreszeit kommst.", mal=2),
        "Ratgeber der Fahrradwerkstatt Radhaus Elbe: Kette ölen, Reifendruck, Fahrrad winterfest machen.")),
    "/blog/winter-check": (200, _seite("Fahrrad winterfest machen | Radhaus Elbe", "Fahrrad winterfest machen",
        _absaetze("Im Winter setzen Salz und Nässe dem Rad zu. Licht prüfen, Kette öfter pflegen und Reifen mit "
                  "etwas weniger Druck fahren – dann kommst du sicher durch die dunkle Jahreszeit.")
        + "<h2>Licht und Reflektoren</h2>" + _absaetze(
            "Prüfe Vorder- und Rücklicht, bevor es früh dunkel wird. Ein Nabendynamo ist im Winter ideal, weil er "
            "nie leer ist. Reflektoren an Speichen und Pedalen machen dich von der Seite sichtbar.", mal=2)
        + "<h2>Kette und Schaltung</h2>" + _absaetze(
            "Streusalz greift die Kette an. Wische sie nach Fahrten auf nassen Straßen ab und öle sie etwa alle zwei "
            "Wochen mit Nassöl. Die Schaltung freut sich über einen Tropfen Öl an den Gelenken.", mal=2)
        + "<h2>Reifen und Bremsen</h2>" + _absaetze(
            "Mit etwas weniger Luftdruck haftet der Reifen besser auf nassem Laub und Schnee. Bremsbeläge "
            "verschleißen im Winter schneller, deshalb lohnt ein Blick darauf im November und im Februar.", mal=2),
        "Fahrrad winterfest machen: Checkliste für Licht, Kette, Reifen und Bremsen, damit du sicher durch den "
        "Winter kommst.", '<meta property="og:type" content="article">')),
    "/faq": (200, _seite("Häufige Fragen | Radhaus Elbe", "Häufige Fragen",
        "<h2>Brauche ich einen Termin?</h2><p>Nur für die große Inspektion. Kleine Reparaturen wie Schlauchwechsel "
        "oder Bremsen einstellen machen wir meist sofort, während du wartest.</p>"
        "<h2>Kann ich mit Karte zahlen?</h2><p>Ja, mit EC- und Kreditkarte, außerdem bar und per Überweisung für "
        "Firmenkunden mit Dienstrad.</p>"
        "<h2>Reparieren Sie auch Lastenräder?</h2><p>Ja, alle gängigen Modelle mit und ohne Motor. Für sehr große "
        "Räder rufst du am besten vorher kurz an, damit wir Platz am Montageständer einplanen.</p>"
        "<h2>Wie lange dauert eine Reparatur?</h2><p>Die meisten Reparaturen sind am selben Tag fertig, wenn du "
        "dein Rad bis 10 Uhr bringst. Müssen wir Teile bestellen, dauert es zwei bis drei Werktage.</p>"
        "<h2>Bekomme ich vorher einen Kostenvoranschlag?</h2><p>Ja, immer. Wir schauen uns das Rad an, nennen dir "
        "den Preis und fangen erst an, wenn du zugestimmt hast. Taucht unterwegs etwas Neues auf, rufen wir an.</p>"
        "<h2>Reparieren Sie Räder, die nicht bei Ihnen gekauft wurden?</h2><p>Natürlich. Die meisten Räder in "
        "unserer Werkstatt stammen aus anderen Läden oder aus dem Internet, das ist für uns kein Problem.</p>"
        "<h2>Gibt es ein Leihrad während der Reparatur?</h2><p>Ja, auf Wunsch bekommst du für die Dauer der "
        "Reparatur ein Citybike kostenlos. Ein E-Bike als Ersatz kostet 15 Euro am Tag.</p>"
        "<h2>Holen Sie mein Rad auch ab?</h2><p>Im Umkreis von drei Kilometern holen wir dein Rad für 15 Euro ab "
        "und bringen es nach der Reparatur zurück. Sag uns einfach, wo es steht und wann du da bist.</p>"
        "<h2>Machen Sie auch Dienstrad-Inspektionen?</h2><p>Ja, wir arbeiten mit den großen Leasing-Anbietern "
        "zusammen und rechnen die Inspektion direkt mit ihnen ab, wenn sie im Vertrag enthalten ist.</p>",
        "Antworten auf häufige Fragen zu Termin, Zahlung und Reparatur.")),
    "/angebote": (200, _seite("Angebote | Radhaus Elbe", "Angebote",
        '<p>Aktuell: 10 % auf alle Inspektionen im März. Alle Preise findest du unter <a href="/preise">Preise</a>.'
        "</p>" + _absaetze(
            "Im Frühjahr wollen alle gleichzeitig wieder losfahren, deshalb belohnen wir alle, die früh dran sind. "
            "Wer im März zur Inspektion kommt, spart zehn Prozent auf die Arbeitszeit.",
            "Für Familien gibt es das Paket aus zwei Inspektionen und einer Kinderrad-Durchsicht für 149 Euro. "
            "Kinderräder wachsen schnell heraus, deshalb stellen wir dabei auch Sattel und Lenker neu ein.",
            "Studierende mit gültigem Ausweis bekommen das ganze Jahr fünf Prozent auf Reparaturen. Sprich uns "
            "beim Abgeben einfach darauf an, dann vermerken wir den Rabatt auf dem Auftrag.", mal=3),
        "Aktuelle Angebote der Fahrradwerkstatt.")),
    "/impressum": (200, _seite("Impressum | Radhaus Elbe", "Impressum",
        "<p>Radhaus Elbe GmbH (erfunden), Musterstraße 1, 20000 Hamburg.</p>", "Impressum", NOINDEX)),
    "/datenschutz": (200, _seite("Datenschutz | Radhaus Elbe", "Datenschutz",
        _absaetze("Wir verarbeiten deine Daten nur, um Reparaturaufträge abzuwickeln.", mal=2), "Datenschutz",
        NOINDEX)),
})
DATEIEN_NACHHER = dict(DATEIEN)
DATEIEN_NACHHER["/sitemap.xml"] = (
    "application/xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    + "".join(f"<url><loc>{{basis}}{p.lstrip('/')}</loc></url>" for p in SEITEN_NACHHER
              if SEITEN_NACHHER[p][0] == 200 and NOINDEX not in SEITEN_NACHHER[p][1])
    + "</urlset>")


class Handler(BaseHTTPRequestHandler):
    seiten, dateien = SEITEN, DATEIEN

    def _antwort(self, mit_body: bool):
        pfad = self.path.split("?")[0]
        basis = f"http://{self.headers.get('Host')}/"
        if pfad in self.seiten:
            status, inhalt = self.seiten[pfad]
            typ = "text/html; charset=utf-8"
        elif pfad in self.dateien:
            status, (typ, inhalt) = 200, self.dateien[pfad]
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


class HandlerNachher(Handler):
    seiten, dateien = SEITEN_NACHHER, DATEIEN_NACHHER


def starten(port: int = 0, nachher: bool = False) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", port), HandlerNachher if nachher else Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/"


if __name__ == "__main__":
    import sys
    nachher = "--nachher" in sys.argv
    zahlen = [a for a in sys.argv[1:] if a.isdigit()]
    port = int(zahlen[0]) if zahlen else 8798
    print(f"Radhaus Elbe (Demo{', nachher' if nachher else ''}) läuft auf http://127.0.0.1:{port}/")
    ThreadingHTTPServer(("127.0.0.1", port), HandlerNachher if nachher else Handler).serve_forever()
