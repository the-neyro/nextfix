"""Service: Themen-Lücke zu einem Mitbewerber (Ersatz für Semrush „Keyword Gap“ ohne SERP-Daten).

Grundlage sind die letzten fertigen Crawls beider Projekte: Wortgruppen (1–3 Wörter) aus den
verschiedenen Titles und H1 der HTML-Seiten. Eine Lücke ist eine Wortgruppe, die beim Mitbewerber in
mindestens zwei Texten vorkommt, bei dir in keinem. „seiten_mitbewerber“ zählt verschiedene Texte. Ohne Rankings oder Suchvolumen – es zeigt Themen, nicht Traffic.
"""

import sqlite3
from collections import Counter, defaultdict

from app.core import audit, projekte
from app.keywords import analyse

MAX_ANTEIL = 0.4      # Wortgruppen in mehr als 40 % der Texte sind Vorlagen-Text (z. B. Firmenname im Title)
MIN_SEITEN = 2


class LueckenFehler(ValueError):
    """Kein Crawl o. Ä."""


def _seiten(conn, projekt_id: int) -> tuple[list[dict], str]:
    p = projekte.holen(conn, projekt_id)
    crawl_id = audit.letzter_crawl_id(conn, projekt_id)
    if not crawl_id:
        raise LueckenFehler(f"{p.name}: noch kein fertiger Crawl")
    zeilen = conn.execute(
        "SELECT url, title, h1_text FROM seiten WHERE crawl_id = ? AND status_code = 200 AND blockiert = 0"
        " AND (title IS NOT NULL OR h1_text IS NOT NULL)", (crawl_id,)).fetchall()
    return [dict(z) for z in zeilen], p.domain


def wortgruppen(text: str, ausschluss: set[str]) -> set[str]:
    """Alle 1–3-Wort-Gruppen ohne Füllwörter am Rand und ohne Markennamen."""
    w = [x for x in analyse.woerter(text) if len(x) > 1 and not x.isdigit()]
    gruppen = set()
    for n in (1, 2, 3):
        for i in range(len(w) - n + 1):
            teil = w[i:i + n]
            if teil[0] in analyse.STOPWOERTER or teil[-1] in analyse.STOPWOERTER:
                continue
            if any(t in ausschluss for t in teil) or not analyse.lesbar(" ".join(teil)):
                continue
            gruppen.add(" ".join(teil))
    return gruppen


def _zaehlen(seiten: list[dict], domain: str) -> tuple[Counter, dict[str, str]]:
    """Zählt, in wie vielen verschiedenen Titles/H1 eine Wortgruppe steckt. Gleiche Texte zählen einmal,
    damit Vorlagen (identische H1 auf vielen Seiten) nicht als Thema durchgehen."""
    marke = {domain.removeprefix("www.").split(".")[0]}
    texte: dict[str, str] = {}
    for s in seiten:
        for feld in (s["title"], s["h1_text"]):
            if feld and feld.strip():
                texte.setdefault(" ".join(feld.lower().split()), s["url"])
    anzahl, beispiel = Counter(), {}
    for text, url in texte.items():
        for g in wortgruppen(text, marke):
            anzahl[g] += 1
            beispiel.setdefault(g, url)
    grenze = max(MIN_SEITEN, MAX_ANTEIL * len(texte))
    return Counter({g: n for g, n in anzahl.items() if n <= grenze or len(texte) < 5}), beispiel


def luecke(conn: sqlite3.Connection, projekt_id: int, mitbewerber_id: int, limit: int = 200) -> dict:
    """Wortgruppen, die der Mitbewerber auf ≥ 2 Seiten nutzt und du auf keiner. Längere Gruppen zuerst gewichtet."""
    if projekt_id == mitbewerber_id:
        raise LueckenFehler("Mitbewerber muss ein anderes Projekt sein")
    eigene, eigene_domain = _seiten(conn, projekt_id)
    fremde, fremde_domain = _seiten(conn, mitbewerber_id)
    eigen, _ = _zaehlen(eigene, eigene_domain)
    fremd, beispiel = _zaehlen(fremde, fremde_domain)
    fremd_marke = {fremde_domain.removeprefix("www.").split(".")[0]}
    eigen_text = " ".join(f"{s['title'] or ''} {s['h1_text'] or ''}".lower() for s in eigene)
    treffer = []
    for g, n in fremd.items():
        if n < MIN_SEITEN or g in eigen or g in eigen_text or g in fremd_marke:
            continue
        treffer.append({"begriff": g, "woerter": len(g.split()), "seiten_mitbewerber": n, "beispiel": beispiel[g]})
    # Teilgruppen ausblenden, wenn eine längere Gruppe mit gleicher Seitenzahl sie enthält
    nach_zahl = defaultdict(list)
    for t in treffer:
        nach_zahl[t["seiten_mitbewerber"]].append(t["begriff"])
    treffer = [t for t in treffer if not any(t["begriff"] != a and f" {t['begriff']} " in f" {a} "
                                              for a in nach_zahl[t["seiten_mitbewerber"]])]
    treffer.sort(key=lambda t: (-(t["seiten_mitbewerber"] * (1 + 0.5 * (t["woerter"] - 1))), t["begriff"]))
    gemeinsam = sum(1 for g in fremd if g in eigen)
    return {"projekt": eigene_domain, "mitbewerber": fremde_domain, "seiten_eigen": len(eigene),
            "seiten_mitbewerber": len(fremde), "gemeinsam": gemeinsam, "luecken": treffer[:limit],
            "luecken_gesamt": len(treffer)}
