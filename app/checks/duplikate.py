"""Checks: Duplicate Content (ähnlicher Haupttext) und strukturierte Daten."""

from itertools import combinations

from app.checks.inhalt import INDEXIERBAR, KANONISCH
from app.checks.katalog import check, json_spalte
from app.crawler.texte import aehnlichkeit

AEHNLICH_AB = 0.85
BAND = 4   # Werte pro Band: Seiten mit einem gleichen Band sind Kandidaten (LSH), spart den Vergleich aller Paare


def _kandidaten(signaturen: dict[int, list[int]]) -> set[tuple[int, int]]:
    eimer: dict[tuple, list[int]] = {}
    for seite_id, sig in signaturen.items():
        for start in range(0, len(sig), BAND):
            eimer.setdefault((start, *sig[start:start + BAND]), []).append(seite_id)
    paare = set()
    for ids in eimer.values():
        paare.update(combinations(sorted(ids), 2))
    return paare


@check("duplicate_content", f"Doppelter Inhalt (≥ {AEHNLICH_AB:.0%} ähnlich)", "warning", "inhalt",
       "Fast gleicher Haupttext auf mehreren URLs: Google wählt selbst eine Version, die anderen erscheinen meist "
       "nicht. Eine Strafe gibt es dafür nicht, aber du verschenkst Seiten.",
       "Inhalte zusammenführen, deutlich unterscheiden oder per Canonical auf die Hauptversion verweisen.")
def duplicate_content(conn, crawl_id):
    zeilen = json_spalte(conn, crawl_id, "signatur", f"{KANONISCH} AND {INDEXIERBAR}")   # noindex: Google sieht sie nicht
    signaturen = {seite_id: sig for seite_id, _, sig in zeilen}
    urls = {seite_id: url for seite_id, url, _ in zeilen}
    partner: dict[int, list[tuple[float, int]]] = {}
    for a, b in _kandidaten(signaturen):
        wert = aehnlichkeit(signaturen[a], signaturen[b])
        if wert >= AEHNLICH_AB:
            partner.setdefault(a, []).append((wert, b))
            partner.setdefault(b, []).append((wert, a))
    treffer = []
    for seite_id, liste in sorted(partner.items()):
        wert, bester = max(liste)
        mehr = f" und {len(liste) - 1} weitere" if len(liste) > 1 else ""
        treffer.append((seite_id, f"{wert:.0%} wie {urls[bester]}{mehr}"))
    return treffer


@check("markup_fehlerhaft", "Fehlerhafte strukturierte Daten", "error", "technik",
       "Fehlerhaftes JSON-LD oder fehlende Pflichtfelder verhindern Rich Results im Suchergebnis.",
       "JSON-Syntax korrigieren und Pflichtfelder des jeweiligen schema.org-Typs ergänzen.")
def markup_fehlerhaft(conn, crawl_id):
    return [(seite_id, "; ".join(m["fehler"][:3]))
            for seite_id, _, m in json_spalte(conn, crawl_id, "markup") if m.get("fehler")]
