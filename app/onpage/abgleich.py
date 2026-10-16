"""Keyword-Abgleich: Regeln wie im Semrush On Page SEO Checker (Strategie, Inhalt, Technik, Links, UX).

Jede Regel hat ein Gewicht (3 = wichtig, 1 = Feinschliff). ok=None heißt „nicht anwendbar“ (zählt nicht).
Treffer sind tolerant: Groß/klein, Umlaute (ü = ue), Bindestriche und Plural-Endungen werden angeglichen.
"""

import re
from dataclasses import asdict, dataclass

from app.keywords.analyse import STOPWOERTER
from app.onpage.seite import Seite

TITLE_MAX, META_MIN, META_MAX = 70, 70, 160
WOERTER_MIN = 300
DICHTE_MAX = 3.0   # % – darüber wirkt der Text überoptimiert
ERSETZEN = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


@dataclass
class Pruefung:
    id: str
    kategorie: str     # Inhalt | Technik | Links | Semantik | Nutzer & KI
    titel: str
    gewicht: int
    ok: bool | None
    detail: str = ""
    tipp: str = ""
    vorschlag: str = ""   # konkreter Formulierungsvorschlag (nur einige Regeln)

    def als_dict(self) -> dict:
        return asdict(self)


def norm(text: str) -> str:
    t = text.lower()
    for a, b in ERSETZEN.items():
        t = t.replace(a, b)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def kern(keyword: str) -> list[str]:
    """Wörter des Keywords ohne Füllwörter („seo für anfänger“ → seo, anfaenger)."""
    woerter = norm(keyword).split()
    return [w for w in woerter if w not in _STOP] or woerter


def phrase_in(keyword: str, text: str) -> bool:
    return f" {norm(keyword)} " in f" {norm(text)} "


def woerter_in(keyword: str, text: str) -> bool:
    """Alle Kernwörter vorhanden (auch gebeugt/Plural: Wortanfang ab 4 Zeichen)."""
    tokens = norm(text).split()
    return all(any(t == w or (len(w) >= 4 and t.startswith(w)) for t in tokens) for w in kern(keyword))


_STOP = {norm(w) for w in STOPWOERTER}


def anzahl(keyword: str, text: str) -> int:
    return f" {norm(text)} ".count(f" {norm(keyword)} ")


def pruefen(s: Seite, keyword: str, eingehend: dict | None = None, vitals: dict | None = None,
            mitbewerber_woerter: int | None = None) -> list[Pruefung]:
    """eingehend: {"links": n, "mit_keyword": n} aus dem Crawl (None = Seite nicht gecrawlt).
    vitals: letzte mobile Messung {"lcp", "cls", "tbt"} oder None. mitbewerber_woerter: Median der Mitbewerber."""
    p: list[Pruefung] = []

    def regel(id_, kat, titel, gewicht, ok, detail="", tipp="", vorschlag=""):
        p.append(Pruefung(id_, kat, titel, gewicht, ok, detail, "" if ok else tipp, "" if ok else vorschlag))

    # ---------- Inhalt ----------
    im_title = phrase_in(keyword, s.title) or woerter_in(keyword, s.title)
    regel("title_keyword", "Inhalt", "Keyword im Title", 3, im_title, s.title or "(kein Title)",
          f"„{keyword}“ in den Title aufnehmen, möglichst weit vorn.", title_vorschlag(keyword, s.title))
    if im_title:
        vorn = norm(s.title).find(norm(kern(keyword)[0])) <= len(norm(s.title)) // 2
        regel("title_vorn", "Inhalt", "Keyword in der vorderen Title-Hälfte", 1, vorn, "",
              "Keyword an den Anfang des Titles ziehen; Markenname nach hinten.")
    regel("h1_keyword", "Inhalt", "Keyword in der H1", 2, any(woerter_in(keyword, h) for h in s.h1),
          " | ".join(s.h1) or "(keine H1)", f"Die H1 so formulieren, dass „{keyword}“ vorkommt.",
          f"{_gross(keyword)}: {s.h1[0]}" if s.h1 else _gross(keyword))
    regel("h1_eine", "Inhalt", "Genau eine H1", 1, len(s.h1) == 1, f"{len(s.h1)} H1",
          "Eine einzige H1 als Hauptüberschrift verwenden.")
    regel("meta_keyword", "Inhalt", "Keyword in der Meta-Description", 1,
          woerter_in(keyword, s.meta_description) if s.meta_description else False,
          s.meta_description or "(keine Meta-Description)",
          "Meta-Description mit dem Keyword und einem klaren Nutzen schreiben (sie wird im Suchergebnis fett).")
    regel("url_keyword", "Inhalt", "Keyword in der URL", 1,
          None if s.slug in ("", "/") else woerter_in(keyword, s.slug.replace("/", " ")),  # Startseite: egal
          s.slug, "Bei neuen Seiten das Keyword in die URL nehmen (bestehende URLs nur mit 301 ändern).")
    regel("text_anfang", "Inhalt", "Keyword in den ersten 100 Wörtern", 2, woerter_in(keyword, s.anfang), "",
          "Das Thema gleich im ersten Absatz nennen.")
    n = anzahl(keyword, s.text)
    dichte = round(100 * n * max(len(norm(keyword).split()), 1) / max(s.woerter, 1), 1)
    if dichte > DICHTE_MAX:
        regel("text_haeufigkeit", "Inhalt", "Keyword-Häufigkeit natürlich", 1, False, f"{n}× ({dichte} %)",
              "Keyword seltener verwenden, Synonyme und verwandte Begriffe nutzen (wirkt sonst überoptimiert).")
    else:
        regel("text_haeufigkeit", "Inhalt", "Keyword mehrfach im Text", 1, n >= 2 or woerter_in(keyword, s.text),
              f"{n}× als Phrase ({dichte} %)", "Keyword (oder seine Wörter) im Text mehrfach natürlich verwenden.")
    regel("zwischen_keyword", "Inhalt", "Keyword-Bezug in Zwischenüberschriften (H2/H3)", 1,
          any(woerter_in(keyword, h) or any(w in norm(h).split() for w in kern(keyword)) for h in s.zwischen)
          if s.zwischen else False, f"{len(s.zwischen)} Zwischenüberschriften",
          "Text mit H2/H3 gliedern und das Keyword oder Teile davon in einer Zwischenüberschrift aufgreifen.")
    ziel = max(WOERTER_MIN, round(0.8 * mitbewerber_woerter)) if mitbewerber_woerter else WOERTER_MIN
    regel("textlaenge", "Inhalt", "Ausreichend Text", 2, s.woerter >= ziel,
          f"{s.woerter} Wörter" + (f", Mitbewerber Ø {mitbewerber_woerter}" if mitbewerber_woerter else ""),
          f"Inhalt auf mindestens {ziel} Wörter ausbauen – mit echtem Mehrwert, nicht mit Füllsätzen.")
    if s.bilder:
        regel("bilder_alt", "Inhalt", "Bilder mit Alt-Text, eines mit Keyword-Bezug", 1,
              s.bilder_ohne_alt == 0 and any(woerter_in(keyword, a) or any(w in norm(a).split() for w in kern(keyword))
                                             for a in s.alt_texte),
              f"{s.bilder} Bilder, {s.bilder_ohne_alt} ohne Alt",
              "Allen Bildern einen beschreibenden Alt-Text geben, beim Hauptbild mit Keyword-Bezug.")

    # ---------- Technik ----------
    indexierbar = s.status == 200 and "noindex" not in s.meta_robots and (
        not s.canonical or norm(s.canonical.rstrip("/")) == norm(s.url.rstrip("/")))
    regel("indexierbar", "Technik", "Seite indexierbar (200, kein noindex, Canonical auf sich selbst)", 3, indexierbar,
          f"Status {s.status}" + (f", Canonical {s.canonical}" if s.canonical else "") +
          (", noindex" if "noindex" in s.meta_robots else ""),
          "Nur indexierbare Seiten können ranken: noindex entfernen bzw. Canonical auf diese URL setzen.")
    snippet_ok = 10 < len(s.title) <= TITLE_MAX and META_MIN <= len(s.meta_description) <= META_MAX
    regel("snippet_laenge", "Technik", "Title und Meta-Description in passender Länge", 1, snippet_ok,
          f"Title {len(s.title)}, Meta {len(s.meta_description)} Zeichen",
          f"Title bis {TITLE_MAX}, Meta-Description {META_MIN}–{META_MAX} Zeichen, damit nichts abgeschnitten wird.")
    regel("schema", "Technik", "Strukturierte Daten vorhanden", 1, bool(s.schema_typen),
          ", ".join(s.schema_typen) or "keine",
          "schema.org-Markup ergänzen (z. B. Article, Product, FAQPage, LocalBusiness) für Rich Results.")
    if vitals:
        gut = (vitals.get("lcp") or 0) <= 2500 and (vitals.get("cls") or 0) <= 0.1 and (vitals.get("tbt") or 0) <= 200
        regel("vitals", "Technik", "Core Web Vitals mobil gut", 2, gut,
              f"LCP {vitals.get('lcp')} ms, CLS {vitals.get('cls')}, TBT {vitals.get('tbt')} ms",
              "Ladezeit verbessern: großes Bild/Schrift zuerst laden, Layout-Sprünge und lange Skripte vermeiden.")

    # ---------- Links ----------
    if eingehend is not None:
        regel("interne_links", "Links", "Mindestens 3 interne Links auf die Seite", 2, eingehend["links"] >= 3,
              f"{eingehend['links']} eingehende interne Links",
              "Von thematisch passenden Seiten intern auf diese Seite verlinken.")
        regel("anker_keyword", "Links", "Interner Ankertext mit Keyword", 1, eingehend["mit_keyword"] >= 1,
              f"{eingehend['mit_keyword']} Ankertexte mit Keyword",
              f"Mindestens einen internen Link mit dem Ankertext „{keyword}“ (oder nah dran) setzen.")

    # ---------- Nutzer & KI ----------
    regel("hauptbereich", "Nutzer & KI", "Hauptinhalt in <main>/<article>", 1, s.hat_hauptbereich, "",
          "Hauptinhalt in <main> fassen – hilft Suchmaschinen und KI-Assistenten, den eigentlichen Text zu finden.")
    regel("lesbarkeit", "Nutzer & KI", "Gut lesbar (Absätze, Sätze, Gliederung)", 1, not s.lesbarkeit,
          "; ".join(s.lesbarkeit), "Lange Absätze teilen, Sätze kürzen, Überschriften ohne Sprünge.")
    return p


AKRONYME = {"ki", "seo", "sea", "ai", "it", "crm", "erp", "api", "dsgvo", "gpt", "llm", "b2b", "b2c", "pdf", "ux",
            "ui", "gmbh", "usa", "eu", "pc", "tv", "diy", "faq"}


def _gross(text: str) -> str:
    """Keyword für Vorschläge schreiben: Akronyme groß (KI, SEO), sonst nur der Anfang groß."""
    woerter = [w.upper() if w.lower() in AKRONYME else w for w in text.split()]
    satz = " ".join(woerter)
    return satz[:1].upper() + satz[1:]


def title_vorschlag(keyword: str, title: str) -> str:
    """Keyword nach vorn, Marke dahinter, höchstens TITLE_MAX Zeichen. Marke = kürzester Teil (nach | – -)."""
    teile = [t.strip() for t in re.split(r"\s[|–—-]\s", title or "") if t.strip()]
    marke = min(teile, key=len) if len(teile) > 1 else ""
    rest = next((t for t in teile if t != marke), "")
    kw = _gross(keyword)
    for kandidat in (f"{kw}: {rest} | {marke}", f"{kw}: {rest}", f"{kw} | {marke}", kw):
        kandidat = kandidat.strip(" :|")
        if len(kandidat) <= TITLE_MAX:
            return kandidat
    return kw


def score(pruefungen: list[Pruefung]) -> int:
    zaehlen = [x for x in pruefungen if x.ok is not None]
    gesamt = sum(x.gewicht for x in zaehlen)
    return round(100 * sum(x.gewicht for x in zaehlen if x.ok) / gesamt) if gesamt else 0
