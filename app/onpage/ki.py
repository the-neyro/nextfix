"""KI-Score (GEO): Wie gut kann eine KI-Suche (ChatGPT, Perplexity, Google AI Overviews) die Seite zitieren?

Unabhängig vom Keyword. Gleiche Signale wie die KI-Checks im Site Audit (app/crawler/geo.py, app/checks/ki.py),
hier als Score 0–100 je Seite. Gewichte: 2 = laut GEO-Studie (Princeton 2024) wirksam, 1 = Feinschliff.
"""

from app.checks.ki import FAQ_TYPEN, MIN_WOERTER_BELEGE
from app.onpage.abgleich import Pruefung, score
from app.onpage.seite import Seite

KATEGORIE = "KI-Suche"


def pruefen(s: Seite) -> list[Pruefung]:
    g = s.geo
    p: list[Pruefung] = []

    def regel(id_, titel, gewicht, ok, detail="", tipp=""):
        p.append(Pruefung(id_, KATEGORIE, titel, gewicht, ok, detail, "" if ok else tipp))

    lang = s.woerter >= MIN_WOERTER_BELEGE
    regel("ki_umfang", f"Genug Text zum Zitieren (≥ {MIN_WOERTER_BELEGE} Wörter)", 1, lang, f"{s.woerter} Wörter",
          "Die Kernfrage der Seite ausführlicher beantworten: Fakten, Beispiele, Ablauf.")
    regel("ki_hauptbereich", "Hauptinhalt in <main>/<article>", 2, s.hat_hauptbereich, "",
          "Hauptinhalt in <main> fassen, damit KI-Systeme Navigation und Fuß nicht mitlesen.")
    regel("ki_gliederung", "Gegliedert mit Zwischenüberschriften (≥ 2)", 2,
          g.get("zwischen", 0) >= 2 if lang else None, f"{g.get('zwischen', 0)} H2/H3",
          "Mit H2/H3 in Abschnitte teilen – KI-Antworten zitieren einzelne Abschnitte.")
    regel("ki_listen", "Listen oder Tabellen", 1, g.get("listen", 0) >= 1 if lang else None,
          f"{g.get('listen', 0)} Listen/Tabellen", "Aufzählungen, Schritte und Vergleiche als Liste oder Tabelle zeigen.")
    regel("ki_zahlen", "Konkrete Zahlen und Statistiken", 2, g.get("zahlen", 0) >= 1, f"{g.get('zahlen', 0)} gefunden",
          "Aussagen mit Zahlen belegen (%, €, Mengen) – laut GEO-Studie häufiger zitiert.")
    regel("ki_quellen", "Links auf externe Quellen", 2, g.get("quellen", 0) >= 1, f"{g.get('quellen', 0)} Domains",
          "Wichtige Aussagen mit Links auf vertrauenswürdige Quellen (Studien, Behörden, Fachseiten) belegen.")
    regel("ki_fragen", "Fragen als Zwischenüberschriften", 1, g.get("fragen", 0) >= 1, f"{g.get('fragen', 0)} Fragen",
          "Typische Nutzerfragen als H2/H3 formulieren und direkt darunter in 1–3 Sätzen beantworten.")
    regel("ki_faq_markup", "FAQ-Markup für Frage-Antwort-Paare", 1,
          bool(FAQ_TYPEN & set(s.schema_typen)) if g.get("fragen", 0) >= 2 else None, "",
          "Die Fragen und Antworten als FAQPage (JSON-LD) auszeichnen.")
    regel("ki_markup", "Strukturierte Daten vorhanden", 1, bool(s.schema_typen), ", ".join(s.schema_typen[:5]),
          "Passendes Schema.org-Markup ergänzen (Article, Product, Organization …).")
    artikel = g.get("artikel", False)
    regel("ki_datum", "Datum angegeben (Aktualität)", 2 if artikel else 1, bool(g.get("datum")), "",
          "datePublished/dateModified im Markup und sichtbar mit <time datetime> angeben.")
    regel("ki_autor", "Autor angegeben (Artikel)", 2, bool(g.get("autor")) if artikel else None, "",
          "Autor mit Namen im Article-Markup (author) und sichtbar am Artikel nennen.")
    regel("ki_lesbarkeit", "Gut lesbar (Absätze, Sätze, Gliederung)", 1, not s.lesbarkeit, "; ".join(s.lesbarkeit),
          "Absätze kürzen, Sätze teilen, Überschriften ohne Sprünge.")
    return p


def bewerten(s: Seite) -> dict:
    pruefungen = pruefen(s)
    return {"score": score(pruefungen), "pruefungen": [x.als_dict() for x in pruefungen]}
