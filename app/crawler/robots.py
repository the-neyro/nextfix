"""robots.txt so auslegen wie Google (RFC 9309): Platzhalter * und $, längste passende Regel gewinnt,
bei Gleichstand gewinnt Allow. Pythons urllib.robotparser kennt weder Platzhalter noch diesen Vorrang.
"""

import re
from urllib.parse import urlsplit


def _muster(pfad: str) -> re.Pattern:
    ende = pfad.endswith("$")
    kern = re.escape(pfad.rstrip("$")).replace(r"\*", ".*")
    return re.compile(kern + ("$" if ende else ""))


class RobotsTxt:
    """Ohne parse() ist alles erlaubt (keine robots.txt oder nicht abrufbar)."""

    def __init__(self):
        self._gruppen: list[tuple[list[str], list[tuple[bool, str]]]] = []   # (User-Agents, [(erlaubt, Pfad)])
        self._sitemaps: list[str] = []

    def parse(self, zeilen: list[str]) -> None:
        agenten: list[str] = []
        regeln: list[tuple[bool, str]] = []
        for zeile in zeilen:
            zeile = zeile.removeprefix("\ufeff").split("#", 1)[0].strip()   # BOM am Dateianfang ignorieren
            if ":" not in zeile:
                continue
            feld, wert = (t.strip() for t in zeile.split(":", 1))
            feld = feld.lower()
            if feld == "user-agent":
                if regeln:   # neue Gruppe beginnt
                    self._gruppen.append((agenten, regeln))
                    agenten, regeln = [], []
                agenten.append(wert.lower())
            elif feld in ("allow", "disallow") and agenten:
                if wert:   # leeres Disallow erlaubt alles, leeres Allow sagt nichts
                    regeln.append((feld == "allow", wert))
            elif feld == "sitemap" and wert:
                self._sitemaps.append(wert)
        if agenten:
            self._gruppen.append((agenten, regeln))

    def site_maps(self) -> list[str]:
        return list(self._sitemaps)

    def _regeln_fuer(self, agent: str) -> list[tuple[bool, str]]:
        """Regeln der genauesten Gruppe: Produktname des Bots (vor dem „/“), sonst „*“."""
        token = agent.split("/", 1)[0].strip().lower()
        bester, regeln = -1, []
        for agenten, gruppe in self._gruppen:
            for a in agenten:
                laenge = 0 if a == "*" else len(a) if token.startswith(a) else -1
                if laenge > bester:
                    bester, regeln = laenge, list(gruppe)
                elif laenge == bester and laenge >= 0:
                    regeln += gruppe   # gleiche Gruppe mehrfach in der Datei: Regeln zusammenlegen
        return regeln

    def can_fetch(self, agent: str, url: str) -> bool:
        teile = urlsplit(url)
        pfad = (teile.path or "/") + (f"?{teile.query}" if teile.query else "")
        bester: tuple[int, bool] | None = None   # (Länge der Regel, erlaubt)
        for erlaubt, regel in self._regeln_fuer(agent):
            if _muster(regel).match(pfad):
                kandidat = (len(regel), erlaubt)
                if bester is None or kandidat > bester:   # länger gewinnt, bei Gleichstand Allow (True > False)
                    bester = kandidat
        return True if bester is None else bester[1]
