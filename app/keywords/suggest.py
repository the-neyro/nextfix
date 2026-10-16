"""Keyword-Ideen aus Google Suggest (Autovervollständigung).

Inoffizieller Endpunkt, keine API. Deshalb sparsam: jede Anfrage wird 30 Tage
gecacht, zwischen echten Anfragen liegt eine Pause, und bei 403/429 wird sofort
abgebrochen (Teilergebnisse bleiben). Pro Recherche etwa 45 Anfragen.
"""

import json
import sqlite3
import time

import httpx

URL = "https://suggestqueries.google.com/complete/search"
CACHE_TAGE = 30
PAUSE_SEKUNDEN = 1.0
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SeoTool/0.1 (privat, lokal)"

W_FRAGEN = ["was ist", "wie", "warum", "welche", "wo", "wann", "wer", "kann man"]
MODIFIKATOREN = ["kostenlos", "kaufen", "preis", "test", "vergleich", "erfahrungen", "für", "mit", "ohne",
                 "vs", "beispiel", "anleitung"]


class SuggestFehler(RuntimeError):
    """Google blockt oder ist nicht erreichbar."""


def teilphrasen(seed: str) -> list[str]:
    """Für Nischen-Begriffe mit mehreren Wörtern: zusammenhängende Teilphrasen mit einem Wort weniger, die das
    längste (spezifischste) Wort enthalten. „webagentur hamburg“ → [„webagentur“]."""
    w = seed.split()
    if len(w) < 2:
        return []
    laengstes = max(w, key=len)
    n = len(w) - 1
    return [" ".join(w[i:i + n]) for i in range(len(w) - n + 1) if laengstes in w[i:i + n]]


def teil_erweiterungen(seed: str) -> list[str]:
    """Zusatzanfragen (Teilphrase pur + A–Z), wenn der Hauptbegriff selbst kaum Vorschläge liefert."""
    return [a for t in teilphrasen(" ".join(seed.split()).lower())
            for a in [t] + [f"{t} {b}" for b in "abcdefghijklmnopqrstuvwxyz"]]


def erweiterungen(seed: str) -> list[str]:
    """Anfragen für einen Hauptbegriff: pur, A–Z dahinter, W-Fragen davor, typische Zusätze dahinter."""
    seed = " ".join(seed.split()).lower()
    return ([seed] + [f"{seed} {b}" for b in "abcdefghijklmnopqrstuvwxyz"]
            + [f"{w} {seed}" for w in W_FRAGEN] + [f"{seed} {m}" for m in MODIFIKATOREN])


class Suggest:
    def __init__(self, conn: sqlite3.Connection, sprache: str = "de", land: str = "de",
                 client: httpx.Client | None = None, pause: float = PAUSE_SEKUNDEN):
        self.conn = conn
        self.sprache, self.land = sprache, land
        self.client = client or httpx.Client(timeout=15, headers={"User-Agent": USER_AGENT})
        self.pause = pause
        self._letzte = 0.0
        self.anfragen_echt = 0

    def vorschlaege(self, anfrage: str) -> list[str]:
        z = self.conn.execute(
            "SELECT antwort FROM suggest_cache WHERE anfrage = ? AND sprache = ? AND land = ?"
            " AND julianday('now') - julianday(abgerufen_am) < ?", (anfrage, self.sprache, self.land, CACHE_TAGE)
        ).fetchone()
        if z:
            return json.loads(z["antwort"])
        ergebnis = self._holen(anfrage)
        self.conn.execute("INSERT OR REPLACE INTO suggest_cache (anfrage, sprache, land, antwort) VALUES (?, ?, ?, ?)",
                          (anfrage, self.sprache, self.land, json.dumps(ergebnis, ensure_ascii=False)))
        self.conn.commit()
        return ergebnis

    def _holen(self, anfrage: str) -> list[str]:
        warten = self.pause - (time.monotonic() - self._letzte)
        if warten > 0:
            time.sleep(warten)
        self._letzte = time.monotonic()
        self.anfragen_echt += 1
        try:
            antwort = self.client.get(URL, params={"client": "firefox", "hl": self.sprache, "gl": self.land,
                                                   "ie": "utf-8", "oe": "utf-8", "q": anfrage})
        except httpx.HTTPError as e:
            raise SuggestFehler(f"Google Suggest nicht erreichbar ({type(e).__name__})") from None
        if antwort.status_code in (403, 429):
            raise SuggestFehler(f"Google bremst ({antwort.status_code}). Später erneut versuchen, "
                                "bisherige Ideen bleiben gespeichert.")
        if antwort.status_code != 200:
            raise SuggestFehler(f"Google Suggest antwortet mit {antwort.status_code}")
        try:
            daten = antwort.json()
            return [" ".join(str(v).split()).lower() for v in daten[1]]
        except (ValueError, IndexError, TypeError):
            raise SuggestFehler("Unerwartete Antwort von Google Suggest") from None
