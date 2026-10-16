"""Suchintention und Gruppen für Keyword-Ideen (eigene Regeln, deutsch, keine externen Daten).

Intent wie in Semrush: informational, navigational, kommerziell (commercial), transaktional.
Erkennung über Signalwörter (deutsch + häufige englische, weil Suggest auch englische Begriffe liefert);
ohne Signal gilt informational. Semrush ordnet teils mehrere
Intents zu, wir nur den stärksten (Reihenfolge: transaktional > navigational > kommerziell > informational).
"""

import re
from collections import Counter

TRANSAKTIONAL = {"kaufen", "bestellen", "preis", "preise", "kosten", "günstig", "billig", "angebot", "angebote",
                 "shop", "online-shop", "download", "herunterladen", "buchen", "mieten", "gutschein", "rabatt",
                 "abo", "kündigen", "lieferung", "versand", "bestellung",
                 "buy", "price", "pricing", "cheap", "order", "coupon", "discount", "deal"}
NAVIGATIONAL = {"login", "anmelden", "einloggen", "kontakt", "telefonnummer", "öffnungszeiten",
                "hotline", "kundenservice", "sign", "signin"}
KOMMERZIELL = {"test", "vergleich", "beste", "bester", "bestes", "besten", "erfahrungen", "bewertung",
               "bewertungen", "vs", "oder", "alternative", "alternativen", "top", "empfehlung", "testsieger",
               "anbieter", "review", "seriös", "lohnt",
               "best", "reviews", "compare", "comparison", "versus", "free", "kostenlos", "gratis"}
FRAGEWOERTER = {"was", "wie", "warum", "wieso", "weshalb", "welche", "welcher", "welches", "wo", "wann", "wer",
                "wieviel", "wie viel", "kann", "können", "darf", "muss", "ist", "sind", "gibt",
                "how", "what", "why", "which", "where", "when", "who", "can", "does", "do", "is", "are"}
INFORMATIONAL = {"anleitung", "tipps", "definition", "bedeutung", "beispiel", "beispiele", "erklärung", "lernen",
                 "tutorial", "idee", "ideen", "unterschied", "funktioniert", "selber", "machen"}
STOPWOERTER = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "und", "oder", "für",
               "mit", "ohne", "von", "zu", "zum", "zur", "im", "in", "am", "an", "auf", "bei", "aus", "nach", "ist",
               "was", "wie", "wo", "wer", "wann", "warum", "welche", "kann", "man", "sich", "es", "auch", "nicht", "vs",
               "the", "a", "an", "for", "to", "of", "on", "with", "and", "or", "my", "your", "is", "how", "what",
               "up", "by", "at", "it", "this", "that", "can", "do", "does"}
DEUTSCHE_BUCHSTABEN = set("abcdefghijklmnopqrstuvwxyzäöüß")
INTENTS = ("informational", "navigational", "kommerziell", "transaktional")


def lesbar(keyword: str) -> bool:
    """Nur lateinische Buchstaben inkl. Umlaute (filtert fremdsprachige Suggest-Treffer wie Vietnamesisch)."""
    return all(not c.isalpha() or c in DEUTSCHE_BUCHSTABEN for c in keyword.lower())


def woerter(keyword: str) -> list[str]:
    return re.findall(r"[\wäöüß-]+", keyword.lower())


def ist_frage(keyword: str) -> bool:
    w = woerter(keyword)
    return bool(w) and (w[0] in FRAGEWOERTER or keyword.strip().endswith("?"))


def intent(keyword: str, marke: str | None = None) -> str:
    w = set(woerter(keyword))
    if w & TRANSAKTIONAL:
        return "transaktional"
    if w & NAVIGATIONAL or (marke and marke.lower() in w and len(w) <= 2):
        return "navigational"
    if w & KOMMERZIELL:
        return "kommerziell"
    return "informational"


def gruppieren(keywords: list[str], seed: str) -> dict[str, str]:
    """Gruppe = häufigstes Zusatzwort (ohne Hauptbegriff und Füllwörter), das im Keyword vorkommt.
    Gruppen mit nur einem Keyword landen in „sonstige“; Keywords ohne Zusatzwort in „(Hauptbegriff)“."""
    basis = set(woerter(seed)) | STOPWOERTER
    zusatz = {k: [w for w in woerter(k) if w not in basis and len(w) > 1] for k in keywords}
    haeufigkeit = Counter(w for ws in zusatz.values() for w in set(ws))
    ergebnis = {}
    for k, ws in zusatz.items():
        if not ws:
            ergebnis[k] = "(Hauptbegriff)"
            continue
        ergebnis[k] = max(ws, key=lambda w: (haeufigkeit[w], -ws.index(w)))
    groesse = Counter(ergebnis.values())
    return {k: g if g == "(Hauptbegriff)" or groesse[g] >= 2 else "sonstige" for k, g in ergebnis.items()}
