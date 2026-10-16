"""Zweite Suchmaschine: Bing Webmaster Tools API (per API-Schlüssel) und eine Mock-Quelle dazu.

Was Bing liefert (GetQueryStats): nur die Top-Suchbegriffe, Wochenwerte (ein Datum pro Woche),
Klicks, Impressionen und Ø-Position. Keine Seiten, keine Länder, keine Geräte – diese Felder
bleiben leer. Ein Aufruf liefert die ganze verfügbare Historie; sie wird pro Quelle einmal geholt
und dann tageweise verteilt (der Import fragt Tag für Tag).

Der Schlüssel steckt in der URL (so verlangt es Bing). Deshalb landen URLs nie in Fehlermeldungen.
Einrichtung: docs/anleitung-bing.md
"""

import math
import random
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app import config
from app.gsc.fehler import GscFehler
from app.gsc.mock import EPOCHE, MockQuelle

BASIS = "https://ssl.bing.com/webmaster/api.svc/json"
_DATUM = re.compile(r"/Date\((-?\d+)([+-]\d{4})?\)/")


def schluessel_laden(pfad: Path | None = None) -> str:
    pfad = Path(pfad or config.BING_SCHLUESSEL)
    if not pfad.is_file():
        raise GscFehler(f"Kein Bing-Schlüssel gefunden: {pfad} (Einrichtung: docs/anleitung-bing.md)")
    schluessel = pfad.read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9]{16,64}", schluessel):
        raise GscFehler("Bing-Schlüsseldatei enthält keinen gültigen API-Schlüssel (nur Buchstaben/Ziffern)")
    return schluessel


def bing_datum(wert: str) -> date:
    """'/Date(1316156400000-0700)/' → 2011-09-16 (Ortszeit laut Offset)."""
    m = _DATUM.fullmatch(wert or "")
    if not m:
        raise GscFehler(f"Unbekanntes Datumsformat von Bing: {wert!r}")
    zeit = datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc)
    if m.group(2):
        vorzeichen = 1 if m.group(2)[0] == "+" else -1
        zeit += vorzeichen * timedelta(hours=int(m.group(2)[1:3]), minutes=int(m.group(2)[3:]))
    return zeit.date()


def _wurzel(domain: str) -> str:
    return domain.lower().removeprefix("www.")


class BingApiQuelle:
    name = "bing"

    def __init__(self, schluessel: str | None = None, client: httpx.Client | None = None):
        self._schluessel = schluessel
        self._client = client or httpx.Client(timeout=60)
        self._cache: dict[str, list[dict]] = {}

    @property
    def schluessel(self) -> str:
        if self._schluessel is None:
            self._schluessel = schluessel_laden()
        return self._schluessel

    def _api(self, methode: str, **parameter) -> list:
        try:
            antwort = self._client.get(f"{BASIS}/{methode}", params={**parameter, "apikey": self.schluessel})
        except httpx.HTTPError as e:  # Meldung ohne URL, sie enthält den Schlüssel
            raise GscFehler(f"Bing nicht erreichbar ({type(e).__name__})") from None
        if antwort.status_code != 200:
            try:
                text = antwort.json().get("Message") or ""
            except ValueError:
                text = ""
            hinweis = " – Schlüssel prüfen" if antwort.status_code in (400, 401, 403) else ""
            raise GscFehler(f"Bing-API-Fehler {antwort.status_code}{hinweis}: {text[:200]}".rstrip(": "))
        return antwort.json().get("d") or []

    def properties(self) -> list[dict]:
        """Alle Websites im Bing-Konto (nur bestätigte sind abfragbar)."""
        return sorted(({"property": s["Url"], "berechtigung": "bestätigt" if s.get("IsVerified") else "unbestätigt"}
                       for s in self._api("GetUserSites")), key=lambda s: s["property"])

    def property_finden(self, domain: str) -> str:
        """Bestätigte Website mit gleichem Host (mit/ohne www), https bevorzugt."""
        wurzel = _wurzel(domain)
        passend = [p["property"] for p in self.properties() if p["berechtigung"] == "bestätigt"
                   and _wurzel(urlparse(p["property"]).hostname or "") == wurzel]
        passend.sort(key=lambda p: (not p.startswith("https://"), urlparse(p).hostname != domain.lower(), p))
        if not passend:
            raise GscFehler(f"Keine bestätigte Website für {domain} in Bing Webmaster Tools gefunden")
        return passend[0]

    def abrufen(self, domain: str, von: date, bis: date, property: str | None = None) -> list[dict]:
        prop = property or self.property_finden(domain)
        if prop not in self._cache:
            self._cache[prop] = [_umwandeln(z) for z in self._api("GetQueryStats", siteUrl=prop)
                                 if z.get("Impressions", 0) > 0 and z.get("AvgImpressionPosition", 0) > 0]
        return [z for z in self._cache[prop] if von.isoformat() <= z["datum"] <= bis.isoformat()]


def _umwandeln(z: dict) -> dict:
    return {"datum": bing_datum(z["Date"]).isoformat(), "query": " ".join(z["Query"].split()).lower(),
            "seite": "", "land": "", "geraet": "", "klicks": int(z.get("Clicks", 0)),
            "impressionen": int(z["Impressions"]), "position": round(float(z["AvgImpressionPosition"]), 1)}


class BingMockQuelle:
    """Testdaten im Bing-Format: gleiche Begriffe wie der Google-Mock, Wochenwerte (montags), ca. 8 % der Nachfrage."""
    name = "bing_mock"

    def abrufen(self, domain: str, von: date, bis: date, property: str | None = None) -> list[dict]:
        begriffe = MockQuelle()._begriffe(domain)
        zeilen = []
        tag = von
        while tag <= bis:
            if tag.weekday() == 0:
                t = (tag - EPOCHE).days
                for b in begriffe:
                    r = random.Random(f"bing|{domain}|{b['query']}|{tag}")
                    pos = b["basis"] + b["amp"] * math.sin(2 * math.pi * t / b["periode"] + b["phase"] + 0.5)
                    pos = max(1.0, pos + r.gauss(0, 1.0) - 1)  # Bing rankt kleine Seiten oft etwas besser
                    faktor = 1.0 if pos <= 10 else 0.35 if pos <= 20 else 0.08
                    impressionen = round(b["nachfrage"] * 7 * 0.08 * faktor * r.uniform(0.6, 1.4))
                    if impressionen <= 0:
                        continue
                    klicks = min(impressionen, round(impressionen * (0.3 / pos) * r.uniform(0.5, 1.5)))
                    zeilen.append({"datum": tag.isoformat(), "query": b["query"], "seite": "", "land": "",
                                   "geraet": "", "klicks": klicks, "impressionen": impressionen,
                                   "position": round(pos, 1)})
            tag += timedelta(days=1)
        return zeilen
