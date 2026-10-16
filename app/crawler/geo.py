"""Signale für KI-Suche (GEO): Fragen, Belege, Gliederung, Autor/Datum.

Grundlage: GEO-Studie (Princeton, KDD 2024) – Zahlen, Quellen und klare Gliederung erhöhen die
Chance, in KI-Antworten zitiert zu werden. Ideen teils aus GEO Optimizer (MIT, Auriti Labs).
"""

import re
from urllib.parse import urljoin, urlsplit

# Zahl mit Einheit = Statistik/Fakt, keine Jahreszahl oder Hausnummer
STATISTIK = re.compile(
    r"\d+(?:[.,]\d+)*\s?(?:%|Prozent|percent|€|EUR|\$|Mio\.?|Mrd\.?|Millionen|Milliarden|million|billion)",
    re.I)
ARTIKEL_TYPEN = {"Article", "NewsArticle", "BlogPosting", "TechArticle", "ScholarlyArticle", "Report"}


def _text(node) -> str:
    return " ".join(node.text(separator=" ").split()) if node else ""


def kopf_signale(baum, jsonld: list[str], typen: list[str]) -> dict:
    """Vor dem Entfernen der <script>-Tags aufrufen: Datum, Autor, Artikel-Erkennung."""
    roh = " ".join(jsonld)
    metas = {}
    for meta in baum.css("meta"):
        a = {k.lower(): (v or "") for k, v in meta.attributes.items()}
        schluessel = (a.get("property") or a.get("name") or "").lower()
        if schluessel:
            metas[schluessel] = a.get("content", "").strip()
    datum = bool(re.search(r'"date(Published|Modified)"\s*:\s*"[^"]+', roh)
                 or metas.get("article:published_time") or metas.get("article:modified_time")
                 or baum.css_first("time[datetime]"))
    autor = bool(re.search(r'"author"\s*:', roh) or metas.get("author") or metas.get("article:author")
                 or baum.css_first('[rel~="author"]'))
    artikel = bool(ARTIKEL_TYPEN & set(typen)) or metas.get("og:type") == "article"
    return {"artikel": artikel, "datum": datum, "autor": autor}


def haupt_signale(haupt, basis_url: str) -> dict:
    """Signale im Hauptbereich (ohne Navigation/Fuß)."""
    text = _text(haupt)
    host = _ohne_www(urlsplit(basis_url).hostname)
    quellen = set()
    for a in haupt.css("a[href]"):
        ziel = urlsplit(urljoin(basis_url, (a.attributes.get("href") or "").strip()))
        if ziel.scheme in ("http", "https") and ziel.hostname and _ohne_www(ziel.hostname) != host:
            quellen.add(_ohne_www(ziel.hostname))
    fragen = [_text(h) for h in haupt.css("h2, h3, h4") if _text(h).endswith("?")]
    return {
        "woerter": len(re.findall(r"\w+", text)),
        "zahlen": len(STATISTIK.findall(text)),
        "quellen": len(quellen),
        "fragen": len(fragen),
        "listen": len(haupt.css("ul, ol, table, dl")),
        "zwischen": len(haupt.css("h2, h3")),
    }


def _ohne_www(host: str | None) -> str:
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host
