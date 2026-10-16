"""Interne Link-Stärke (eigene Formel, angelehnt an PageRank).

Graph: erreichbare HTML-Seiten (Status 200) als Knoten, interne follow-Links zwischen ihnen als Kanten
(pro Seitenpaar einmal). PageRank mit Dämpfung 0,85; Seiten ohne ausgehende Links verteilen gleichmäßig.
Skala 0–100 logarithmisch: stärkste Seite = 100, schwächste = 0. So bleiben Unterschiede auch bei
vielen schwach verlinkten Seiten sichtbar.
"""

import math
import sqlite3

DAEMPFUNG = 0.85
RUNDEN = 50


def pagerank(kanten: dict[int, set[int]], knoten: list[int]) -> dict[int, float]:
    n = len(knoten)
    rang = dict.fromkeys(knoten, 1 / n)
    for _ in range(RUNDEN):
        sackgassen = sum(rang[k] for k in knoten if not kanten.get(k))
        neu = dict.fromkeys(knoten, (1 - DAEMPFUNG) / n + DAEMPFUNG * sackgassen / n)
        for quelle, ziele in kanten.items():
            if ziele:
                anteil = DAEMPFUNG * rang[quelle] / len(ziele)
                for ziel in ziele:
                    neu[ziel] += anteil
        rang = neu
    return rang


def skalieren(rang: dict[int, float]) -> dict[int, int]:
    werte = [math.log(r) for r in rang.values()]
    tief, hoch = min(werte), max(werte)
    if hoch - tief < 1e-12:
        return dict.fromkeys(rang, 100)
    return {k: round(100 * (math.log(r) - tief) / (hoch - tief)) for k, r in rang.items()}


def berechnen(conn: sqlite3.Connection, crawl_id: int) -> None:
    """Spalte seiten.link_rank für alle erreichbaren HTML-Seiten des Crawls setzen."""
    ids = dict(conn.execute(
        "SELECT url, id FROM seiten WHERE crawl_id=? AND status_code=200 AND woerter IS NOT NULL", (crawl_id,)))
    if not ids:
        return
    gueltig = set(ids.values())
    kanten: dict[int, set[int]] = {}
    for quelle, ziel_url in conn.execute(
            "SELECT seite_id, ziel_url FROM links WHERE crawl_id=? AND art='a' AND intern=1 AND nofollow=0", (crawl_id,)):
        ziel = ids.get(ziel_url)
        if ziel is not None and ziel != quelle and quelle in gueltig:
            kanten.setdefault(quelle, set()).add(ziel)
    werte = skalieren(pagerank(kanten, list(ids.values())))
    conn.executemany("UPDATE seiten SET link_rank=? WHERE id=?", [(w, k) for k, w in werte.items()])
