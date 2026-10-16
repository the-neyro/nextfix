"""Bewertung einzelner Ressourcen (JS/CSS): Caching und Minifizierung aus Header und Inhalt."""

import re

MIN_BYTES_MINIFY = 2048        # kleine Dateien: Minifizierung lohnt kaum, nicht bewerten
MINIFIZIERT_ZEILE_AB = 200     # Ø Zeichen pro Zeile: ab hier sicher minifiziert
EINGERUECKT_MAX = 0.10         # Anteil eingerückter Zeilen: darüber nicht minifiziert
KOMMENTARE_MAX = 0.02          # Anteil Kommentare (ohne /*! Lizenz */): darüber nicht minifiziert

# Ein Zeilenumbruch pro Regel (z. B. style.min.css) gilt noch als minifiziert: bringt nach gzip kaum etwas
KOMMENTAR = re.compile(r"(?ms)/\*(?!!).*?\*/|^\s*//.*?$")

MAX_AGE = re.compile(r"(?:s-)?max-age\s*=\s*(\d+)", re.I)


def wird_gecacht(cache_control: str | None, expires: str | None) -> bool:
    """True, wenn der Browser die Datei zwischenspeichern darf (max-age > 0 oder Expires)."""
    cc = (cache_control or "").lower()
    if "no-store" in cc or "no-cache" in cc:
        return False
    alter = [int(x) for x in MAX_AGE.findall(cc)]
    if alter:
        return max(alter) > 0
    return "immutable" in cc or bool((expires or "").strip())


def ist_minifiziert(text: str) -> bool | None:
    """None = zu klein zum Bewerten."""
    if len(text) < MIN_BYTES_MINIFY:
        return None
    zeilen = [z for z in text.split("\n") if z.strip()]
    if not zeilen or len(text) / len(zeilen) >= MINIFIZIERT_ZEILE_AB:
        return True
    eingerueckt = sum(z[0] in " \t" for z in zeilen) / len(zeilen)
    kommentare = sum(len(k) for k in KOMMENTAR.findall(text)) / len(text)
    return eingerueckt <= EINGERUECKT_MAX and kommentare <= KOMMENTARE_MAX
