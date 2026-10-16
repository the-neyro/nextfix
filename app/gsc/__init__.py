"""Datenquellen für Position Tracking (Search Console).

Jede Quelle liefert Zeilen im selben Format wie die GSC-API (Search Analytics,
Dimensionen date × query × page × country × device):
    {"datum", "query", "seite", "land", "geraet", "klicks", "impressionen", "position"}

Quellen: gsc (Google Search Console per Service-Account), bing (Bing Webmaster per API-Schlüssel)
und je eine Mock-Quelle mit Testdaten. Jede Quelle gehört zu einer Suchmaschine; deren Daten
werden nie gemischt ausgewertet.
"""

from datetime import date
from typing import Protocol

from app.gsc.api import GscApiQuelle
from app.gsc.bing import BingApiQuelle, BingMockQuelle
from app.gsc.fehler import GscFehler
from app.gsc.mock import MockQuelle

__all__ = ["GscFehler", "Quelle", "QUELLEN", "SUCHMASCHINE", "quelle_holen"]


class Quelle(Protocol):
    name: str

    def abrufen(self, domain: str, von: date, bis: date, property: str | None = None) -> list[dict]: ...


QUELLEN = {"gsc": GscApiQuelle, "mock": MockQuelle, "bing": BingApiQuelle, "bing_mock": BingMockQuelle}
SUCHMASCHINE = {"gsc": "google", "mock": "google", "bing": "bing", "bing_mock": "bing"}
# Quellen mit Zugang (Schlüssel, Property); Mock-Quellen brauchen keinen
MIT_ZUGANG = ("gsc", "bing")


def quelle_holen(name: str) -> Quelle:
    if name not in QUELLEN:
        raise GscFehler(f"Unbekannte Quelle: {name} ({' | '.join(QUELLEN)})")
    return QUELLEN[name]()
