"""Mock-Quelle: erzeugt plausible Search-Console-Daten ohne Google-Zugang.

Deterministisch: gleiche Domain + gleicher Tag ergeben immer dieselben Werte,
auch wenn sich Abrufzeiträume überschneiden. Enthält bewusst Gewinner, Verlierer,
Kannibalisierung (zwei Seiten für einen Begriff) und Begriffe auf Position 8–20.
"""

import itertools
import math
import random
from datetime import date, timedelta

from app.gsc.ctr import erwartete_ctr

THEMEN = [
    "seo tool kostenlos", "website prüfen", "seo check", "ki texte schreiben", "chatgpt alternative",
    "keyword recherche", "backlinks prüfen", "ranking verbessern", "meta description länge",
    "ladezeit optimieren", "sitemap erstellen", "robots txt beispiel", "canonical tag", "hreflang",
    "strukturierte daten", "core web vitals", "duplicate content", "interne verlinkung",
    "title tag länge", "alt text bilder", "seo für anfänger", "google search console",
    "404 fehler finden", "weiterleitung 301", "llms txt",
]
# Begriffe, für die zwei Seiten konkurrieren (Kannibalisierung)
DOPPELT = {"seo check", "keyword recherche", "interne verlinkung"}
GERAETE = {"MOBILE": 0.6, "DESKTOP": 0.4}
# Nachfrage relativ zu Deutschland; im Ausland rankt die Seite etwas schlechter
LAENDER = {"deu": 1.0, "aut": 0.15, "che": 0.1}
EPOCHE = date(2026, 1, 1)


def _slug(text: str) -> str:
    return text.replace(" ", "-")


class MockQuelle:
    name = "mock"

    def abrufen(self, domain: str, von: date, bis: date, property: str | None = None) -> list[dict]:
        begriffe = self._begriffe(domain)
        zeilen = []
        tag = von
        while tag <= bis:
            for b in begriffe:
                zeilen += self._tag(domain, b, tag)
            tag += timedelta(days=1)
        return zeilen

    def _begriffe(self, domain: str) -> list[dict]:
        """Feste Eigenschaften je Suchbegriff (Basisposition, Schwankung, Nachfrage)."""
        marke = domain.removeprefix("www.").split(".")[0]
        r = random.Random(f"begriffe|{domain}")
        begriffe = [
            {"query": marke, "seiten": ["/"], "basis": 1.2, "amp": 0.2, "periode": 90, "phase": 0, "nachfrage": 300},
            {"query": f"{marke} erfahrungen", "seiten": ["/"], "basis": 3.0, "amp": 1.5,
             "periode": 70, "phase": 1, "nachfrage": 60},
        ]
        for thema in THEMEN:
            seiten = [f"/{_slug(thema)}/"]
            if thema in DOPPELT:
                seiten.append(f"/blog/{_slug(thema)}-tipps/")
            begriffe.append({
                "query": thema, "seiten": seiten,
                "basis": r.uniform(2, 45), "amp": r.uniform(0, 9),
                "periode": r.uniform(50, 180), "phase": r.uniform(0, 2 * math.pi),
                "nachfrage": r.choice([20, 40, 80, 150, 400, 900]),
            })
        return begriffe

    def _tag(self, domain: str, b: dict, tag: date) -> list[dict]:
        t = (tag - EPOCHE).days
        zeilen = []
        for (land, land_anteil), (geraet, geraet_anteil) in itertools.product(LAENDER.items(), GERAETE.items()):
            r = random.Random(f"{domain}|{b['query']}|{tag}|{geraet}" + ("" if land == "deu" else f"|{land}"))
            anteil = land_anteil * geraet_anteil
            pos = b["basis"] + b["amp"] * math.sin(2 * math.pi * t / b["periode"] + b["phase"])
            pos = max(1.0, pos + r.gauss(0, 0.6) + (0 if land == "deu" else r.uniform(0, 4)))
            for i, seite in enumerate(b["seiten"]):
                # zweite Seite rankt schlechter und bekommt weniger Impressionen
                p = pos + i * r.uniform(3, 8)
                faktor = 1.0 if p <= 10 else 0.35 if p <= 20 else 0.08
                impressionen = round(b["nachfrage"] * anteil * faktor * r.uniform(0.7, 1.3) / (1 + i))
                if impressionen <= 0:
                    continue  # GSC liefert keine Zeilen ohne Impressionen
                klicks = min(impressionen, round(impressionen * erwartete_ctr(p) * r.uniform(0.6, 1.4)))
                zeilen.append({
                    "datum": tag.isoformat(), "query": b["query"], "seite": f"https://{domain}{seite}",
                    "land": land, "geraet": geraet, "klicks": klicks,
                    "impressionen": impressionen, "position": round(p, 1),
                })
        return zeilen
