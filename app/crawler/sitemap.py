"""Sitemaps laden: XML, Sitemap-Index (rekursiv), gzip. Liefert Dateien und URL-Einträge."""

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

from app.crawler.urls import normalisieren

MAX_DATEIEN = 50
MAX_BYTES = 50 * 1024 * 1024      # Grenze laut sitemaps.org (unkomprimiert)
MAX_URLS_PRO_DATEI = 50_000
MAX_EINTRAEGE = 100_000           # Schutz vor riesigen Sitemaps


@dataclass
class SitemapDatei:
    url: str
    status: int | None = None
    bytes: int = 0
    url_anzahl: int = 0
    ist_index: bool = False
    fehler: str | None = None


@dataclass
class SitemapErgebnis:
    dateien: list[SitemapDatei] = field(default_factory=list)
    eintraege: list[tuple[str, str]] = field(default_factory=list)   # (url, sitemap_url)


def laden(client: httpx.Client, start_urls: list[str]) -> SitemapErgebnis:
    ergebnis = SitemapErgebnis()
    offen, gesehen = list(start_urls), set()
    while offen and len(ergebnis.dateien) < MAX_DATEIEN:
        url = offen.pop(0)
        if url in gesehen:
            continue
        gesehen.add(url)
        datei, kinder, eintraege = _datei_laden(client, url)
        ergebnis.dateien.append(datei)
        offen.extend(kinder)
        platz = MAX_EINTRAEGE - len(ergebnis.eintraege)
        ergebnis.eintraege.extend((e, url) for e in eintraege[:max(platz, 0)])
    return ergebnis


def _datei_laden(client: httpx.Client, url: str) -> tuple[SitemapDatei, list[str], list[str]]:
    datei = SitemapDatei(url=url)
    try:
        r = client.get(url, follow_redirects=True)
    except httpx.HTTPError as fehler:
        datei.fehler = f"{type(fehler).__name__}: {fehler}"[:200]
        return datei, [], []
    datei.status = r.status_code
    if r.status_code != 200:
        return datei, [], []

    inhalt = r.content
    if inhalt[:2] == b"\x1f\x8b":  # gzip, unabhängig von der Endung
        try:
            inhalt = gzip.decompress(inhalt)
        except (OSError, EOFError) as fehler:
            datei.fehler = f"gzip: {fehler}"
            return datei, [], []
    datei.bytes = len(inhalt)

    try:
        wurzel = ET.fromstring(inhalt)
    except ET.ParseError as fehler:
        datei.fehler = f"XML: {fehler}"
        return datei, [], []

    name = wurzel.tag.rsplit("}", 1)[-1]
    locs = [(e.text or "").strip() for e in wurzel.iter() if e.tag.rsplit("}", 1)[-1] == "loc"]
    if name == "sitemapindex":
        datei.ist_index = True
        datei.url_anzahl = len(locs)
        return datei, [l for l in locs if l], []
    if name != "urlset":
        datei.fehler = f"Unerwartetes Wurzelelement <{name}> (erwartet urlset oder sitemapindex)"
        return datei, [], []
    datei.url_anzahl = len(locs)
    leer = sum(1 for l in locs if not l)
    if leer:
        datei.fehler = f"{leer} leere <loc>-Einträge"
    return datei, [], [n for n in (normalisieren(l, l) for l in locs if l) if n]
