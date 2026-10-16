"""Seite lesen: alles, was der On-Page-Abgleich braucht (Title, Überschriften, Text, Bilder, Technik)."""

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.crawler import parser


@dataclass
class Seite:
    url: str
    status: int = 0
    title: str = ""
    meta_description: str = ""
    h1: list[str] = field(default_factory=list)
    zwischen: list[str] = field(default_factory=list)   # H2 und H3 in Reihenfolge
    text: str = ""                                        # Hauptinhalt (main/article, sonst body ohne Navigation)
    woerter: int = 0
    bilder: int = 0
    bilder_ohne_alt: int = 0
    alt_texte: list[str] = field(default_factory=list)
    canonical: str | None = None
    meta_robots: str = ""
    schema_typen: list[str] = field(default_factory=list)
    hat_hauptbereich: bool = False
    lesbarkeit: list[str] = field(default_factory=list)
    geo: dict = field(default_factory=dict)              # KI-Signale aus app/crawler/geo.py

    @property
    def slug(self) -> str:
        return urlsplit(self.url).path

    @property
    def anfang(self) -> str:
        """Die ersten 100 Wörter des Hauptinhalts."""
        return " ".join(self.text.split()[:100])


def _text(node) -> str:
    return " ".join(node.text(separator=" ").split()) if node else ""


def lesen(html: str, url: str, status: int = 200) -> Seite:
    basis = parser.zerlegen(html, url)
    s = Seite(url=url, status=status, title=basis.title or "", meta_description=basis.meta_description or "",
              h1=basis.h1, canonical=basis.canonicals[0] if basis.canonicals else None,
              meta_robots=(basis.meta_robots or "").lower(), schema_typen=basis.markup.get("typen", []),
              lesbarkeit=basis.lesbarkeit, geo=basis.geo, hat_hauptbereich=any(t in basis.semantik for t in ("main", "article")))
    baum = HTMLParser(html)
    for tag in baum.css("script, style, noscript, template"):
        tag.decompose()
    s.zwischen = [_text(h) for h in baum.css("h2, h3") if _text(h)]
    bilder = baum.css("img")
    s.bilder = len(bilder)
    s.bilder_ohne_alt = sum(1 for b in bilder if not (b.attributes.get("alt") or "").strip())
    s.alt_texte = [(b.attributes.get("alt") or "").strip() for b in bilder if (b.attributes.get("alt") or "").strip()]
    s.text = _text(parser.hauptbereich(baum))
    s.woerter = len(re.findall(r"\w+", s.text))
    return s
