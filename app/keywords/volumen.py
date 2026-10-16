"""Suchvolumen aus Bing (GetKeywordStats): wöchentliche Bing-Impressionen je Suchbegriff.

Das ist KEIN Google-Suchvolumen. Wir zeigen es ehrlich als „Bing-Impressionen pro Monat“
(Ø der letzten 13 Wochen × 52 / 12) und den Wochenverlauf als Trend. Ohne Hochrechnung auf Google.

Parameter-Format für country/language ist in der Bing-Doku nicht beschrieben; Standard „de“ / „de-DE“ [ungeprüft].
Jeder Begriff wird 30 Tage gecacht (volumen_cache).
"""

import json
import random
import sqlite3
import time

from app.gsc import bing
from app.gsc.fehler import GscFehler

CACHE_TAGE = 30
WOCHEN = 13
PAUSE_SEKUNDEN = 0.3
SPRACHEN = {"de": "de-DE", "at": "de-AT", "ch": "de-CH", "en": "en-US"}


def monatswert(wochen: list[int]) -> int | None:
    if not wochen:
        return None
    letzte = wochen[-WOCHEN:]
    return round(sum(letzte) / len(letzte) * 52 / 12)


class BingVolumen:
    name = "bing"

    def __init__(self, conn: sqlite3.Connection, land: str = "de", sprache: str = "de",
                 quelle: bing.BingApiQuelle | None = None, pause: float = PAUSE_SEKUNDEN):
        self.conn, self.land = conn, land.lower()
        self.sprache = SPRACHEN.get(sprache.lower(), sprache)
        self.quelle = quelle
        self.pause = pause
        self._letzte = 0.0

    def holen(self, keyword: str) -> dict:
        """{"monat": int | None, "verlauf": [Wochenwerte]} – aus dem Cache oder von Bing."""
        z = self.conn.execute(
            "SELECT monat, verlauf FROM volumen_cache WHERE keyword = ? AND land = ? AND sprache = ? AND quelle = ?"
            " AND julianday('now') - julianday(abgerufen_am) < ?",
            (keyword, self.land, self.sprache, self.name, CACHE_TAGE)).fetchone()
        if z:
            return {"monat": z["monat"], "verlauf": json.loads(z["verlauf"])}
        verlauf = self._wochen(keyword)
        ergebnis = {"monat": monatswert(verlauf), "verlauf": verlauf}
        self.conn.execute("INSERT OR REPLACE INTO volumen_cache (keyword, land, sprache, quelle, monat, verlauf)"
                          " VALUES (?, ?, ?, ?, ?, ?)", (keyword, self.land, self.sprache, self.name,
                                                         ergebnis["monat"], json.dumps(verlauf)))
        self.conn.commit()
        return ergebnis

    def _wochen(self, keyword: str) -> list[int]:
        warten = self.pause - (time.monotonic() - self._letzte)
        if warten > 0:
            time.sleep(warten)
        self._letzte = time.monotonic()
        q = self.quelle or bing.BingApiQuelle()
        self.quelle = q
        zeilen = q._api("GetKeywordStats", q=keyword, country=self.land, language=self.sprache)
        werte = sorted((bing.bing_datum(z["Date"]), int(z.get("Impressions") or 0)) for z in zeilen if z.get("Date"))
        return [w for _, w in werte]


class BingVolumenMock(BingVolumen):
    """Testwerte ohne Schlüssel: deterministisch je Begriff, kürzere Begriffe = mehr Volumen."""
    name = "bing_mock"

    def _wochen(self, keyword: str) -> list[int]:
        r = random.Random(f"volumen|{keyword}")
        if r.random() < 0.15:
            return []  # Bing kennt den Begriff nicht
        basis = r.choice([5, 10, 20, 40, 80, 160, 400]) * 3 / max(len(keyword.split()), 1)
        steigung = r.uniform(-0.03, 0.04)
        return [max(0, round(basis * (1 + steigung * i) * r.uniform(0.7, 1.3))) for i in range(26)]


VOLUMEN_QUELLEN = {"bing": BingVolumen, "bing_mock": BingVolumenMock}

__all__ = ["BingVolumen", "BingVolumenMock", "GscFehler", "VOLUMEN_QUELLEN", "monatswert"]
