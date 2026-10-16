"""Textanalyse: Haupttext finden, Ähnlichkeits-Signatur (MinHash), Lesbarkeit."""

import hashlib
import random
import re

WORT = re.compile(r"\w+", re.UNICODE)
SATZENDE = re.compile(r"[.!?]+(?:\s|$)")

SIGNATUR_LAENGE = 64
SHINGLE = 3                     # Wort-Dreiergruppen
MIN_WOERTER_SIGNATUR = 50       # kürzere Texte: keine Signatur (zu wenig Inhalt für einen Vergleich)
ABSATZ_MAX_WOERTER = 150
SATZ_MAX_WOERTER = 25

# Feste Masken = stabile Signaturen über Prozesse hinweg
_MASKEN = random.Random(20261014).sample(range(1, 2**63), SIGNATUR_LAENGE)


def woerter(text: str) -> list[str]:
    return WORT.findall(text.lower())


def signatur(text: str) -> list[int] | None:
    """MinHash über Wort-Shingles. Gleicher Anteil gleicher Werte ≈ Jaccard-Ähnlichkeit."""
    w = woerter(text)
    if len(w) < MIN_WOERTER_SIGNATUR:
        return None
    hashes = {
        int.from_bytes(hashlib.blake2b(" ".join(w[i:i + SHINGLE]).encode(), digest_size=8).digest(), "big")
        for i in range(len(w) - SHINGLE + 1)
    }
    return [min(h ^ m for h in hashes) for m in _MASKEN]


def aehnlichkeit(a: list[int], b: list[int]) -> float:
    return sum(x == y for x, y in zip(a, b)) / len(a)


def lesbarkeit(absaetze: list[str], ueberschriften: list[int]) -> list[str]:
    """Probleme für KI-/Nutzer-freundlichen Inhalt. ueberschriften: Ebenen in Reihenfolge (1..6)."""
    probleme = []
    lang = [len(woerter(a)) for a in absaetze if len(woerter(a)) > ABSATZ_MAX_WOERTER]
    if lang:
        probleme.append(f"{len(lang)} Absatz/Absätze über {ABSATZ_MAX_WOERTER} Wörter")
    for vorher, jetzt in zip(ueberschriften, ueberschriften[1:]):
        if jetzt > vorher + 1:
            probleme.append(f"Überschriften-Sprung H{vorher} → H{jetzt}")
            break
    text = " ".join(absaetze)
    saetze = [s for s in SATZENDE.split(text) if woerter(s)]
    if len(saetze) >= 5:
        schnitt = sum(len(woerter(s)) for s in saetze) / len(saetze)
        if schnitt > SATZ_MAX_WOERTER:
            probleme.append(f"Lange Sätze (Ø {schnitt:.0f} Wörter)")
    return probleme
