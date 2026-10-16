"""Strukturierte Daten: JSON-LD und Microdata erkennen und grob validieren.

Validierung bewusst einfach: gültiges JSON, @context/@type vorhanden und Pflichtfelder
für die wichtigsten Typen mit Google-Rich-Results.
"""

import json

# Pflichtfelder nach Google-Dokumentation (Auswahl der häufigsten Rich-Result-Typen)
PFLICHTFELDER = {
    "Article": ("headline",), "NewsArticle": ("headline",), "BlogPosting": ("headline",),
    "Product": ("name",),
    "Organization": ("name",), "LocalBusiness": ("name", "address"),
    "BreadcrumbList": ("itemListElement",),
    "FAQPage": ("mainEntity",), "Question": ("name", "acceptedAnswer"),
    "Event": ("name", "startDate", "location"),
    "Recipe": ("name", "image"),
    "JobPosting": ("title", "datePosted", "description", "hiringOrganization"),
    "VideoObject": ("name", "thumbnailUrl", "uploadDate"),
    "Review": ("itemReviewed", "author"),
    "Person": ("name",),
}


def jsonld_auswerten(bloecke: list[str]) -> dict:
    """bloecke: Inhalte der <script type="application/ld+json">-Tags."""
    typen, fehler = [], []
    for nr, text in enumerate(bloecke, 1):
        try:
            daten = json.loads(text)
        except json.JSONDecodeError as e:
            fehler.append(f"JSON-LD #{nr}: ungültiges JSON ({e.msg}, Zeile {e.lineno})")
            continue
        objekte = daten if isinstance(daten, list) else [daten]
        for obj in objekte:
            if not isinstance(obj, dict):
                fehler.append(f"JSON-LD #{nr}: Eintrag ist kein Objekt")
                continue
            if "@context" not in obj:
                fehler.append(f"JSON-LD #{nr}: @context fehlt")
            knoten = obj.get("@graph") if isinstance(obj.get("@graph"), list) else [obj]
            for k in knoten:
                _knoten_pruefen(k, nr, typen, fehler)
    return {"typen": typen, "fehler": fehler}


def _knoten_pruefen(k, nr: int, typen: list, fehler: list) -> None:
    if not isinstance(k, dict):
        return
    typ = k.get("@type")
    if typ is None:
        fehler.append(f"JSON-LD #{nr}: @type fehlt")
        return
    for t in typ if isinstance(typ, list) else [typ]:
        t = str(t)
        typen.append(t)
        fehlend = [f for f in PFLICHTFELDER.get(t, ()) if k.get(f) in (None, "", [])]
        if fehlend:
            fehler.append(f"{t}: Pflichtfeld(er) fehlen: {', '.join(fehlend)}")


def microdata_typen(itemtypes: list[str]) -> list[str]:
    """'https://schema.org/Product' → 'Product'."""
    return [t.rstrip("/").rsplit("/", 1)[-1] for t in itemtypes if t]
