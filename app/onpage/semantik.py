"""Semantische Ideen: verwandte Begriffe (Google Suggest, Mitbewerber), Fragen für einen FAQ-Block."""

from collections import Counter

from app.keywords.analyse import STOPWOERTER, ist_frage
from app.onpage.abgleich import kern, norm

MAX_BEGRIFFE = 15
MAX_FRAGEN = 8
# Füllwörter in normalisierter Schreibweise (für → fuer), sonst rutschen sie durch
LEERE_WOERTER = {norm(w) for w in STOPWOERTER | {
    "mehr", "sowie", "ihre", "ihr", "sie", "wir", "uns", "unsere", "alle", "noch", "nur", "sehr", "kann", "können",
    "werden", "wird", "sind", "haben", "hat", "dass", "oder", "einfach", "jetzt", "hier", "dabei", "dazu", "über",
    "unter", "zwischen", "durch", "heißt", "heisst", "nennt", "bedeutet", "gibt", "machen", "macht"}}


def _woerter(text: str) -> list[str]:
    return [w for w in norm(text).split() if len(w) >= 4 and not w.isdigit() and w not in LEERE_WOERTER]


def _bigramme(text: str) -> list[str]:
    w = [x for x in norm(text).split() if not x.isdigit()]
    return [f"{a} {b}" for a, b in zip(w, w[1:])
            if a not in LEERE_WOERTER and b not in LEERE_WOERTER and len(a) >= 3 and len(b) >= 3]


def vorhanden(begriff: str, text_norm: str) -> bool:
    return f" {begriff} " in f" {text_norm} " or (len(begriff) >= 6 and begriff in text_norm)


def aus_suggest(vorschlaege: list[str], keyword: str, seiten_text: str, ausschluss: set[str] = frozenset()) -> list[dict]:
    """Begriffe, die in mehreren Suggest-Vorschlägen neben dem Keyword stehen (= wonach Leute dazu suchen).
    ausschluss: Wörter, die wir selbst an die Anfragen gehängt haben (sonst zählen sie sich selbst hoch)."""
    eigen = set(kern(keyword)) | set(norm(keyword).split()) | set(ausschluss)
    zaehler = Counter(w for v in vorschlaege for w in set(_woerter(v)) if w not in eigen)
    text = norm(seiten_text)
    return [{"begriff": b, "vorkommen": n, "auf_seite": vorhanden(b, text)}
            for b, n in zaehler.most_common() if n >= 2][:MAX_BEGRIFFE]


def fragen(vorschlaege: list[str], seiten_text: str, zwischen: list[str], keyword: str = "") -> list[dict]:
    """Fragen aus Suggest. „beantwortet“, wenn eine Zwischenüberschrift mit demselben Fragewort beginnt und die
    übrigen Wörter der Frage (ohne das Keyword) fast alle enthält."""
    eigen = set(kern(keyword)) | set(norm(keyword).split())
    ueber = [norm(h).split() for h in zwischen]
    ergebnis = []
    for f in dict.fromkeys(v for v in vorschlaege if ist_frage(v)):
        teile = norm(f).split()
        rest = [w for w in _woerter(f) if w not in eigen]
        beantwortet = any(h and h[0] == teile[0] and sum(w in h for w in rest) >= max(0, len(rest) - 1)
                          and (rest or any(w in h for w in eigen)) for h in ueber)
        ergebnis.append({"frage": f, "beantwortet": beantwortet})
    return ergebnis[:MAX_FRAGEN]


def aus_mitbewerbern(texte: list[str], keyword: str, seiten_text: str) -> list[dict]:
    """Begriffe (1–2 Wörter), die mehrere Mitbewerber verwenden, die Seite aber nicht."""
    if not texte:
        return []
    eigen = set(kern(keyword)) | set(norm(keyword).split())
    dokumente, gesamt = Counter(), Counter()
    for t in texte:
        begriffe = _woerter(t) + _bigramme(t)
        gesamt.update(begriffe)
        dokumente.update(set(begriffe))
    mindest = 2 if len(texte) >= 2 else 1
    text = norm(seiten_text)
    kandidaten = [(b, d) for b, d in dokumente.items()
                  if d >= mindest and b not in eigen and not vorhanden(b, text) and gesamt[b] >= 2]
    # bei gleicher Verbreitung das genauere Wortpaar vor dem Einzelwort
    kandidaten.sort(key=lambda x: (-x[1], -len(x[0].split()), -gesamt[x[0]], x[0]))
    # Einzelwort weglassen, wenn ein gewähltes Wortpaar es schon enthält
    gewaehlt: list[str] = []
    for b, _ in kandidaten:
        if not any(b in g.split() for g in gewaehlt):
            gewaehlt.append(b)
        if len(gewaehlt) == MAX_BEGRIFFE:
            break
    return [{"begriff": b, "mitbewerber": dokumente[b], "vorkommen": gesamt[b]} for b in gewaehlt]
