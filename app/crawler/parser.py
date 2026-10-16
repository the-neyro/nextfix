"""HTML einer Seite in strukturierte Daten zerlegen (selectolax/Lexbor)."""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.crawler import geo, markup, texte
from app.crawler.urls import normalisieren

SEMANTIK_TAGS = ("main", "article", "section", "nav", "header", "footer", "aside")
PLUGIN_MUSTER = re.compile(r"flash|shockwave|\.swf\b|java|\.jar\b|\.class\b|silverlight|\.xap\b", re.I)


@dataclass
class Link:
    url: str
    art: str                 # a | img | script | css
    anker_text: str | None = None
    nofollow: bool = False
    alt: str | None = None   # nur img; None = Attribut fehlt


@dataclass
class SeitenInhalt:
    title: str | None = None
    meta_description: str | None = None
    h1: list[str] = field(default_factory=list)
    canonicals: list[str] = field(default_factory=list)
    meta_robots: str | None = None
    woerter: int = 0
    text_anteil: float = 0.0
    hat_viewport: bool = False
    viewport_ok: bool = False
    hat_doctype: bool = False
    hat_charset: bool = False
    hat_meta_refresh: bool = False
    lang: str | None = None
    hat_frames: bool = False
    links: list[Link] = field(default_factory=list)
    hreflang: list[dict] = field(default_factory=list)     # {"lang", "url", "absolut"}
    markup: dict = field(default_factory=lambda: {"typen": [], "fehler": []})
    signatur: list[int] | None = None
    hat_passwort: bool = False
    plugins: list[str] = field(default_factory=list)
    semantik: list[str] = field(default_factory=list)       # vorhandene semantische Tags
    lesbarkeit: list[str] = field(default_factory=list)     # Probleme
    kaputte_links: list[str] = field(default_factory=list)  # hrefs mit ungültiger Syntax
    geo: dict = field(default_factory=dict)                 # Signale für KI-Suche, siehe geo.py
    blockierend: list[str] = field(default_factory=list)    # externe Skripte im <head> ohne async/defer
    js_app: str | None = None   # leerer App-Container (z. B. "#root"): Inhalt entsteht erst per JavaScript


def _text(node) -> str:
    return " ".join(node.text(separator=" ").split()) if node else ""


def zerlegen(html: str, basis_url: str) -> SeitenInhalt:
    baum = HTMLParser(html)
    inhalt = SeitenInhalt()
    inhalt.hat_doctype = html.lstrip()[:15].lower().startswith("<!doctype")

    # <base href> verändert die Basis für relative Links
    base = baum.css_first("base[href]")
    if base:
        basis_url = urljoin(basis_url, base.attributes.get("href") or "")

    _kopf(baum, inhalt, basis_url)
    _links(baum, inhalt, basis_url)
    _technik(baum, inhalt)

    jsonld = [s.text() for s in baum.css('script[type="application/ld+json"]')]
    inhalt.markup = markup.jsonld_auswerten(jsonld)
    inhalt.markup["typen"] += markup.microdata_typen([n.attributes.get("itemtype") or "" for n in baum.css("[itemscope][itemtype]")])
    inhalt.geo = geo.kopf_signale(baum, jsonld, inhalt.markup["typen"])

    # Sichtbarer Text: ohne script/style/noscript
    for tag in baum.css("script, style, noscript, template"):
        tag.decompose()
    text = _text(baum.body)
    inhalt.woerter = len(re.findall(r"\w+", text))
    inhalt.text_anteil = round(len(text) / len(html), 4) if html else 0.0
    _haupttext(baum, inhalt, basis_url)
    return inhalt


def _kopf(baum, inhalt: SeitenInhalt, basis_url: str) -> None:
    title = baum.css_first("head title") or baum.css_first("title")
    if title:
        inhalt.title = _text(title)

    for meta in baum.css("meta"):
        a = {k.lower(): (v or "") for k, v in meta.attributes.items()}
        name = a.get("name", "").lower()
        if name == "description":
            inhalt.meta_description = a.get("content", "").strip()
        elif name == "robots":
            inhalt.meta_robots = a.get("content", "").strip().lower()
        elif name == "viewport":
            inhalt.hat_viewport = True
            c = a.get("content", "").lower()
            inhalt.viewport_ok = "width" in c or "initial-scale" in c
        if "charset" in a or "charset=" in a.get("content", "").lower():
            inhalt.hat_charset = True
        if a.get("http-equiv", "").lower() == "refresh":
            inhalt.hat_meta_refresh = True

    inhalt.h1 = [_text(h) for h in baum.css("h1")]

    for link in baum.css("link[rel]"):
        rels = (link.attributes.get("rel") or "").lower().split()
        href = link.attributes.get("href")
        if not href:
            continue
        if "canonical" in rels:
            inhalt.canonicals.append(normalisieren(href, basis_url) or urljoin(basis_url, href))
        if "stylesheet" in rels:
            _anhaengen(inhalt, basis_url, href, "css")
        if "alternate" in rels and link.attributes.get("hreflang"):
            inhalt.hreflang.append({
                "lang": link.attributes["hreflang"].strip(),
                "url": urljoin(basis_url, href.strip()),
                "absolut": bool(urlsplit(href.strip()).scheme),
            })

    html_tag = baum.css_first("html")
    if html_tag:
        inhalt.lang = (html_tag.attributes.get("lang") or "").strip() or None


def _links(baum, inhalt: SeitenInhalt, basis_url: str) -> None:
    for a in baum.css("a[href]"):
        href = a.attributes.get("href") or ""
        if kaputter_link(href):
            inhalt.kaputte_links.append(href.strip()[:300])
            continue
        rel = (a.attributes.get("rel") or "").lower().split()
        _anhaengen(inhalt, basis_url, href, "a", anker_text=_linktext(a), nofollow="nofollow" in rel)
    for img in baum.css("img[src]"):
        _anhaengen(inhalt, basis_url, img.attributes.get("src"), "img",
                   alt=img.attributes.get("alt") if "alt" in img.attributes else None)
    for s in baum.css("script[src]"):
        _anhaengen(inhalt, basis_url, s.attributes.get("src"), "script")


# Container, in die React, Vue, Next.js, Nuxt, Gatsby, Angular, Quasar ihre Oberfläche schreiben
APP_CONTAINER = ("#root", "#app", "#__next", "#__nuxt", "#___gatsby", "#q-app", "app-root")
APP_LEER_WOERTER = 20


def _js_app(baum) -> str | None:
    """Selektor des ersten App-Containers ohne nennenswerten Text, falls die Seite Skripte hat."""
    if not baum.css_first("script"):
        return None
    for selektor in APP_CONTAINER:
        node = baum.css_first(selektor)
        if node is not None and len(_text(node).split()) < APP_LEER_WOERTER:
            return selektor
    return None


def _technik(baum, inhalt: SeitenInhalt) -> None:
    inhalt.hat_frames = bool(baum.css_first("frameset, frame"))
    inhalt.hat_passwort = bool(baum.css_first('input[type="password" i]'))
    for node in baum.css("object, embed, applet"):
        merkmale = " ".join(str(v) for v in node.attributes.values()) + (" java" if node.tag == "applet" else "")
        if PLUGIN_MUSTER.search(merkmale):
            inhalt.plugins.append(node.tag)
    inhalt.semantik = [t for t in SEMANTIK_TAGS if baum.css_first(t)]
    inhalt.js_app = _js_app(baum)
    # Render-blockierend: Browser hält den Aufbau an, bis das Skript geladen und ausgeführt ist
    for s in baum.css("head script[src]"):
        a = {k.lower(): (v or "").lower() for k, v in s.attributes.items()}
        if "async" not in a and "defer" not in a and a.get("type") != "module":
            inhalt.blockierend.append(s.attributes.get("src") or "")


def hauptbereich(baum):
    """Hauptinhalt: <main>; sonst ein einzelnes <article> (Blogbeitrag); sonst <body> ohne Kopf, Navigation,
    Fuß und Seitenleisten. Mehrere <article> sind meist Teaser-Karten und nicht der Hauptinhalt.
    Achtung: entfernt bei Bedarf header/nav/footer/aside aus dem Baum."""
    haupt = baum.css_first("main")
    if haupt is None:
        artikel = baum.css("article")
        haupt = artikel[0] if len(artikel) == 1 else None
    if haupt is None:
        for tag in baum.css("header, nav, footer, aside"):
            tag.decompose()
        haupt = baum.body
    return haupt


def _haupttext(baum, inhalt: SeitenInhalt, basis_url: str) -> None:
    """Haupttext ohne Navigation/Kopf/Fuß: Grundlage für Duplicate Content und Lesbarkeit."""
    ebenen = [int(h.tag[1]) for h in baum.css("h1, h2, h3, h4, h5, h6")]
    haupt = hauptbereich(baum)
    if haupt is None:
        return
    absaetze = [_text(p) for p in haupt.css("p")]
    inhalt.signatur = texte.signatur(_text(haupt))
    inhalt.lesbarkeit = texte.lesbarkeit(absaetze, ebenen)
    inhalt.geo.update(geo.haupt_signale(haupt, basis_url))


def kaputter_link(href: str) -> bool:
    """Offensichtlich ungültige Link-Syntax (Tippfehler im Schema, fehlender Host, Leerzeichen)."""
    h = href.strip()
    if not h or h.lower().startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return False  # keine Seiten-Links; Leerzeichen in Telefonnummern sind üblich
    if h.startswith(("/", "?")) and " " not in h:
        return False
    if re.match(r"^https?:/(?!/)", h, re.I) or re.match(r"^https?//", h, re.I):
        return True  # http:/x oder http//x
    schema = re.match(r"^([a-z][a-z0-9+.-]*):", h, re.I)
    if schema and schema.group(1).lower() not in ("http", "https") and re.fullmatch(r"h+t+p+s?", schema.group(1), re.I):
        return True  # htp:, htttp:, …
    if " " in h:
        return True
    try:
        teile = urlsplit(h)
    except ValueError:
        return True
    return teile.scheme in ("http", "https") and not teile.netloc


def _linktext(a) -> str | None:
    """Zugänglicher Name eines Links: Text, sonst aria-label, sonst alt eines Bildes, sonst title."""
    for kandidat in (_text(a), a.attributes.get("aria-label"), _bild_alt(a), a.attributes.get("title")):
        if kandidat and kandidat.strip():
            return kandidat.strip()
    return None


def _bild_alt(a) -> str | None:
    """Anchor-Text eines Bild-Links = alt des Bildes."""
    img = a.css_first("img[alt]")
    if img is None:
        return None
    return (img.attributes.get("alt") or "").strip() or None


def _anhaengen(inhalt: SeitenInhalt, basis: str, href: str | None, art: str, **extra) -> None:
    url = normalisieren(href or "", basis)
    if url:
        inhalt.links.append(Link(url=url, art=art, **extra))
