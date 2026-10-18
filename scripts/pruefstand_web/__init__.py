"""Bausteine des Prüfstands: Test-Websites mit bekannter Wahrheit (Soll) für jede Prüfung von Nextfix.

Jede Seite trägt ihr Soll mit: welche Prüfungen auf ihr anschlagen MÜSSEN (ja) und bei welchen sie ein
Grenzfall ist, bei dem die Prüfung NICHT anschlagen darf (nein). Der Vergleich ist streng: Jeder Treffer,
der nicht als „ja“ erwartet ist, zählt als Fehlalarm (scripts/pruefstand.py).

Alle Seiten sind sonst „sauber“ gebaut (eigener Titel, Beschreibung, eine H1, 220 Wörter im <main>,
Viewport, lang, charset, gzip, Last-Modified), damit jede Seite genau einen Fall prüft.
Alle Inhalte sind erfunden.
"""

import gzip
import html
import random
import re
import struct
import zlib
from dataclasses import dataclass, field

LETZTE_AENDERUNG = "Sat, 17 Oct 2026 08:00:00 GMT"
CACHE = {"Cache-Control": "max-age=31536000"}   # ein Jahr: gilt als gut gecacht
STIL = "body{font-family:sans-serif;max-width:40rem;margin:auto;padding:0 1rem}img{max-width:100%;height:auto}"

WORTSCHATZ = (
    "fahrrad werkstatt kette bremse schaltung reifen ventil sattel lenker pedal rahmen speiche nabe licht "
    "klingel schlauch mantel felge gabel dämpfer akku motor display kabel schraube mutter öl fett lappen bürste "
    "pumpe luftdruck stadt hafen elbe straße brücke regen wind sonne winter sommer frühling herbst morgen abend "
    "kunde termin beratung angebot auftrag rechnung garantie ersatzteil zubehör korb anhänger schloss helm "
    "handschuh jacke tasche karte route tour ausflug strecke hügel ufer park wiese wald dorf markt platz größe "
    "gewicht farbe qualität").split()
# Lange Wörter ohne Umlaute: für Seiten, die auf eine bestimmte Bytegröße kommen sollen
LANGE_WOERTER = ("fahrradwerkstattzubehoer", "inspektionsprotokoll", "bremsbelagwechsel", "schaltungseinstellung",
                 "reifendruckpruefung", "kettenschmierung", "laufradzentrierung", "lichtanlagenpruefung")


def woerter(text: str) -> int:
    """Wörter wie Nextfix sie zählt: Folgen von Buchstaben/Ziffern (Tags werden vorher entfernt)."""
    return len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", text)))


def saetze(saat: str, anzahl: int, satz: int = 10) -> list[str]:
    """`anzahl` zufällige Wörter als Sätze zu je `satz` Wörtern (letzter Satz ggf. kürzer)."""
    z = random.Random(saat)
    w = [z.choice(WORTSCHATZ) for _ in range(anzahl)]
    return [" ".join(w[i:i + satz]).capitalize() + "." for i in range(0, anzahl, satz)]


def absaetze(saat: str, anzahl: int, satz: int = 10, absatz: int = 50) -> str:
    """Genau `anzahl` Wörter als <p>-Absätze zu höchstens `absatz` Wörtern."""
    teile = []
    for start in range(0, anzahl, absatz):
        menge = min(absatz, anzahl - start)
        teile.append("<p>" + " ".join(saetze(f"{saat}-{start}", menge, satz)) + "</p>")
    return "".join(teile)


def auf_laenge(anfang: str, laenge: int, fueller: str = " Fahrradwerkstatt am Elbufer mit Reparatur und Service") -> str:
    """Text mit genau `laenge` Zeichen, ohne Leerzeichen am Rand (Nextfix trimmt Titel und Beschreibung)."""
    text = anfang
    while len(" ".join(text.split())) < laenge:
        text += fueller
    text = " ".join(text.split())[:laenge]
    return text[:-1] + "x" if text.endswith(" ") else text


def png(breite: int, hoehe: int, rauschen: bool = False) -> bytes:
    """Echte PNG-Datei. rauschen=True: zufällige Pixel (Chrome wertet einfarbige Bilder nicht als LCP)."""
    z = random.Random(f"{breite}x{hoehe}")
    zeilen = b"".join(b"\x00" + (z.randbytes(breite * 3) if rauschen else b"\xc8\x50\x28" * breite)
                      for _ in range(hoehe))

    def block(art: bytes, daten: bytes) -> bytes:
        return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + block(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0))
            + block(b"IDAT", zlib.compress(zeilen)) + block(b"IEND", b""))


@dataclass
class Antwort:
    """Was der Server für eine Adresse liefert."""
    status: int = 200
    body: bytes | str = ""
    typ: str | None = "text/html; charset=utf-8"
    header: dict = field(default_factory=dict)
    gzip: bool = True             # komprimieren, wenn der Client gzip annimmt
    verzoegerung: float = 0.0     # Sekunden vor der Antwort (nur GET)
    abbrechen: bool = False       # Verbindung ohne Antwort schließen
    nur_erster_get: bool = False  # ab dem 2. GET Verbindung schließen (z. B. Chromium nach dem Crawler)
    gets: int = 0                 # Zähler dafür

    def daten(self, gzip_erlaubt: bool) -> tuple[bytes, dict]:
        roh = self.body.encode() if isinstance(self.body, str) else self.body
        header = dict(self.header)
        if self.typ:
            header["Content-Type"] = self.typ
        if self.gzip and gzip_erlaubt and roh:
            roh = gzip.compress(roh, mtime=0)
            header["Content-Encoding"] = "gzip"
        return roh, header


@dataclass(frozen=True)
class Soll:
    """Erwartung: Prüfung `check` muss (ja) bzw. darf nicht (nein) anschlagen.
    pfad None = Treffer für die ganze Website; nadel = Text, der dann im Detail stehen muss."""
    check: str
    website: str
    pfad: str | None
    ja: bool
    nadel: str | None = None
    warum: str = ""

    @property
    def ort(self) -> str:
        return f"{self.website}:{self.pfad}" if self.pfad else f"{self.website}:*" + (f" ({self.nadel})" if self.nadel else "")


class Website:
    """Eine lokale Test-Website. basis z. B. http://127.0.0.1:54321/, fremd = Basis des „fremden“ Servers."""

    def __init__(self, name: str, basis: str, fremd: str):
        self.name, self.basis, self.fremd = name, basis.rstrip("/") + "/", fremd.rstrip("/")
        self.antworten: dict[str, Antwort] = {}
        self.menue: list[tuple[str, int]] = []
        self.soll: list[Soll] = []
        self._nr = 0
        # Lokal läuft alles über http:// – dieser Hinweis ist auf jeder Website richtig
        self.erwarte(ja=["startseite_ohne_https"])

    def url(self, pfad: str) -> str:
        return self.basis.rstrip("/") + pfad

    # ---------- Soll ----------

    def erwarte(self, pfad: str | None = None, ja=(), nein=(), warum: dict | None = None) -> None:
        """ja/nein: Check-IDs, für die ganze Website auch (Check-ID, Nadel im Detail)."""
        for wert, liste in ((True, ja), (False, nein)):
            for eintrag in liste:
                check, nadel = eintrag if isinstance(eintrag, tuple) else (eintrag, None)
                self.soll.append(Soll(check, self.name, pfad, wert, nadel, (warum or {}).get(check, "")))

    # ---------- Antworten ----------

    def datei(self, pfad: str, body: bytes | str, typ: str, **antwort) -> None:
        antwort.setdefault("header", dict(CACHE))
        self.antworten[pfad] = Antwort(body=body, typ=typ, **antwort)

    def status(self, pfad: str, code: int, ja=(), nein=(), warum=None, **antwort) -> None:
        self.antworten[pfad] = Antwort(status=code, body=f"<h1>Status {code}</h1>", **antwort)
        self.erwarte(pfad, ja, nein, warum)

    def weiterleitung(self, pfad: str, ziel: str, code: int = 301, ja=(), nein=(), warum=None) -> None:
        self.antworten[pfad] = Antwort(status=code, header={"Location": ziel}, typ=None)
        self.erwarte(pfad, ja, nein, warum)

    def roh(self, pfad: str, text: str, ja=(), nein=(), warum=None, im_menue: bool = True) -> None:
        """HTML-Seite, die nicht ins Raster von seite() passt (z. B. Frameset statt <body>)."""
        self._nr += 1
        self.antworten[pfad] = Antwort(body=text, header={"Last-Modified": LETZTE_AENDERUNG})
        if im_menue:
            self.menue.append((pfad, self._nr))
        self.erwarte(pfad, ja, nein, warum)

    def seite(self, pfad: str, *, titel=None, beschreibung=None, h1=None, inhalt: str | None = None,
              woerter_main: int = 220, kopf: str = "", vor_main: str = "", nach_main: str = "", lang: str | None = "de",
              doctype: str = "<!doctype html>", charset: bool = True,
              viewport: str | None = "width=device-width, initial-scale=1", main_tag: str = "main",
              robots: str | None = None, noindex: bool = False, canonical: str | list[str] | None = None,
              last_modified: bool = True, im_menue: bool = True, ja=(), nein=(), warum: dict | None = None,
              **antwort) -> str:
        """HTML-Seite, sauber bis auf den Fall, den sie prüft. titel/beschreibung/h1: None = Standard,
        False = weglassen. Gibt das HTML zurück."""
        self._nr += 1
        nr = self._nr
        titel = f"Testseite {nr:03d} im Prüfstand von Nextfix" if titel is None else titel
        beschreibung = (f"Testseite {nr:03d} des Prüfstands: Sie prüft genau einen Fall und ist sonst in jeder "
                        "Hinsicht sauber gebaut." if beschreibung is None else beschreibung)
        h1 = f"Testfall {nr:03d}" if h1 is None else h1
        if inhalt is None:
            inhalt = absaetze(pfad, woerter_main - woerter(h1 or ""))
        if noindex:
            robots, ja = "noindex, follow", (*ja, "blockiert")

        kopfteile = ['<meta charset="utf-8">' if charset else ""]
        if viewport is not None:
            kopfteile.append(f'<meta name="viewport" content="{viewport}">')
        if titel is not False:
            kopfteile.append(f"<title>{html.escape(titel)}</title>")
        if beschreibung is not False:
            kopfteile.append(f'<meta name="description" content="{html.escape(beschreibung)}">')
        if robots:
            kopfteile.append(f'<meta name="robots" content="{robots}">')
        for ziel in [canonical] if isinstance(canonical, str) else canonical or []:
            kopfteile.append(f'<link rel="canonical" href="{self.url(ziel)}">')
        kopfteile += ['<link rel="stylesheet" href="/stil.css">', kopf]

        ueberschrift = f"<h1>{html.escape(h1)}</h1>" if h1 is not False else ""
        fuss = ('<footer><a href="/">Startseite des Prüfstands</a> · '
                '<a href="/uebersicht">Alle Testfälle im Überblick</a></footer>')
        lang_attr = f' lang="{lang}"' if lang else ""
        text = (f"{doctype}<html{lang_attr}><head>{''.join(kopfteile)}</head><body>{vor_main}"
                f"<{main_tag}>{ueberschrift}{inhalt}</{main_tag}>{nach_main}{fuss}</body></html>")

        header = {"Last-Modified": LETZTE_AENDERUNG} if last_modified else {}
        header.update(antwort.pop("header", {}))
        self.antworten[pfad] = Antwort(body=text, header=header, **antwort)
        if im_menue:
            self.menue.append((pfad, nr))
        self.erwarte(pfad, ja, nein, warum)
        return text

    def hubs(self, start_kopf: str = "", start_ja=(), start_nein=(), warum=None) -> None:
        """Startseite und Übersicht verlinken alle Menü-Seiten: So hat jede Testseite zwei eingehende Links
        und liegt eine Ebene unter der Startseite."""
        menue = list(self.menue)
        liste = "".join(f'<li><a href="{html.escape(p)}">Testfall {nr:03d}</a></li>' for p, nr in menue)
        nav = f"<nav><ul>{liste}</ul></nav>"
        self.seite("/", titel=f"Prüfstand {self.name}: lokale Test-Website für Nextfix", kopf=start_kopf,
                   nach_main=nav, im_menue=False, ja=start_ja, nein=start_nein, warum=warum)
        self.seite("/uebersicht", titel=f"Alle Testfälle der Website {self.name} im Überblick",
                   nach_main=nav, im_menue=False)
        self.datei("/stil.css", STIL, "text/css")

    def finden(self, pfad: str) -> Antwort | None:
        return self.antworten.get(pfad) or self.antworten.get(pfad.split("?", 1)[0])


ORGANISATION = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization",'
                '"name":"Prüfstand Radhaus (erfunden)","url":"/"}</script>')


def grundausstattung(w: Website, sitemap_pfade: list[str] | None = None, robots_zusatz: str = "") -> None:
    """robots.txt mit Sitemap, sitemap.xml und llms.txt ohne Fehler: für Websites, die nur einzelne Fälle prüfen."""
    w.datei("/robots.txt", f"User-agent: *\nAllow: /\n{robots_zusatz}\nSitemap: {w.basis}sitemap.xml\n",
            "text/plain; charset=utf-8")
    pfade = sitemap_pfade if sitemap_pfade is not None else ["/", "/uebersicht"]
    w.datei("/sitemap.xml", sitemap(w, pfade), "application/xml")
    w.datei("/llms.txt", f"# Prüfstand {w.name}\n\n> Lokale Test-Website für Nextfix, alle Inhalte erfunden.\n\n"
            f"## Seiten\n- [Start]({w.basis}): Einstieg\n- [Übersicht]({w.basis}uebersicht): alle Testfälle\n"
            f"- [Stil]({w.basis}stil.css): Gestaltung\n", "text/plain; charset=utf-8")


def sitemap(w: Website, pfade: list[str]) -> str:
    eintraege = "".join(f"<url><loc>{html.escape(w.url(p))}</loc></url>" for p in pfade)
    return ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{eintraege}</urlset>")
