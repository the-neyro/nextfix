"""Hauptwebsite, Teil KI-Suche: Hauptbereich, Lesbarkeit, Fragen, Belege, Gliederung, Artikel."""

from scripts.pruefstand_web import Website, absaetze, woerter


def _fuellen(w: Website, pfad: str, gesamt: int, *feste: str, h1: str | None = None, **kw) -> None:
    """Seite mit genau `gesamt` Wörtern im Hauptinhalt: zufälliger Text vor jedem festen Teil."""
    nr = w._nr + 1
    h1 = h1 or f"Testfall {nr:03d}"
    rest = gesamt - woerter(h1) - sum(woerter(t) for t in feste)
    anteile = [rest // (len(feste) + 1)] * len(feste)
    anteile.append(rest - sum(anteile))
    inhalt = "".join(absaetze(f"{pfad}-{i}", n) + (feste[i] if i < len(feste) else "") for i, n in enumerate(anteile))
    w.seite(pfad, h1=h1, inhalt=inhalt, **kw)


def hauptbereich(w: Website) -> None:
    w.seite("/ohne-main", main_tag="div", ja=["ki_ohne_hauptbereich"])
    w.seite("/nur-article", main_tag="article", nein=["ki_ohne_hauptbereich"])


def lesbarkeit(w: Website) -> None:
    w.seite("/absatz-151", inhalt=absaetze("absatz-151", 151, absatz=151) + absaetze("absatz-151b", 67),
            ja=["ki_schwer_lesbar"])
    w.seite("/absatz-150", inhalt=absaetze("absatz-150", 150, absatz=150) + absaetze("absatz-150b", 68),
            nein=["ki_schwer_lesbar"])
    w.seite("/ueberschrift-sprung", inhalt=absaetze("sprung-1", 100) + "<h2>Ablauf</h2>" + absaetze("sprung-2", 58)
            + "<h4>Einzelheiten</h4>" + absaetze("sprung-3", 58), ja=["ki_schwer_lesbar"])
    w.seite("/ueberschriften-ok", inhalt=absaetze("stufen-1", 100) + "<h2>Ablauf</h2>" + absaetze("stufen-2", 58)
            + "<h3>Einzelheiten</h3>" + absaetze("stufen-3", 58), nein=["ki_schwer_lesbar"])
    # 8 Sätze à 26 bzw. 25 Wörter (Grenze: Durchschnitt über 25)
    w.seite("/lange-saetze", inhalt=absaetze("lange-saetze", 208, satz=26, absatz=104), ja=["ki_schwer_lesbar"])
    w.seite("/saetze-25", inhalt=absaetze("saetze-25", 200, satz=25, absatz=100), nein=["ki_schwer_lesbar"])


def fragen(w: Website) -> None:
    def frage(t: str) -> str:
        return f"<h2>{t}</h2><p>Meist am selben Tag, sonst nach Absprache.</p>"
    zwei = frage("Wie lange dauert eine Reparatur?") + frage("Brauche ich einen Termin?")
    _fuellen(w, "/fragen-2", 230, zwei, ja=["ki_fragen_ohne_faq"])
    _fuellen(w, "/fragen-1", 230, frage("Wie lange dauert eine Reparatur?"), nein=["ki_fragen_ohne_faq"])
    faq = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":['
           '{"@type":"Question","name":"Wie lange dauert eine Reparatur?","acceptedAnswer":{"@type":"Answer",'
           '"text":"Meist am selben Tag."}},{"@type":"Question","name":"Brauche ich einen Termin?",'
           '"acceptedAnswer":{"@type":"Answer","text":"Nur für die Inspektion."}}]}</script>')
    _fuellen(w, "/fragen-faq", 230, zwei, kopf=faq, nein=["ki_fragen_ohne_faq", "markup_fehlerhaft"])


def belege(w: Website) -> None:
    quelle = f'<p>Quelle: <a href="{w.fremd}/ok/studie">Studie der Fahrradverbände</a></p>'
    _fuellen(w, "/belege-ohne-300", 300, ja=["ki_ohne_belege"])
    _fuellen(w, "/belege-ohne-299", 299, nein=["ki_ohne_belege"])
    _fuellen(w, "/belege-zahl-300", 300, "<p>Anteil 15 %</p>", nein=["ki_ohne_belege"])
    _fuellen(w, "/belege-quelle-300", 300, quelle, nein=["ki_ohne_belege"])
    _fuellen(w, "/datenschutz", 300, nein=["ki_ohne_belege"],
             warum={"ki_ohne_belege": "Rechtstexte brauchen keine Zahlen und Quellen"})


def textwand(w: Website) -> None:
    zahl = "<p>Anteil 15 %</p>"   # damit nur die Gliederung geprüft wird, nicht die Belege
    _fuellen(w, "/textwand-600", 600, zahl, "<h2>Weitere Hinweise</h2>", ja=["ki_textwand"])
    _fuellen(w, "/textwand-599", 599, zahl, "<h2>Weitere Hinweise</h2>", nein=["ki_textwand"])
    _fuellen(w, "/textwand-600-zwei-h2", 600, zahl, "<h2>Weitere Hinweise</h2>", "<h2>Noch mehr Hinweise</h2>",
             nein=["ki_textwand"])
    _fuellen(w, "/textwand-600-liste", 600, zahl, "<ul><li>Bremsen prüfen</li><li>Kette ölen</li></ul>",
             nein=["ki_textwand"])


def artikel(w: Website) -> None:
    w.seite("/artikel-ohne-datum", kopf='<meta property="og:type" content="article">'
            '<meta name="author" content="Mira Beispiel">', ja=["ki_artikel_ohne_autor_datum"])
    _fuellen(w, "/artikel-komplett", 220, '<p><time datetime="2026-10-01">1. Oktober 2026</time></p>',
             kopf='<meta property="og:type" content="article"><meta name="author" content="Mira Beispiel">',
             nein=["ki_artikel_ohne_autor_datum"])


def alles(w: Website) -> None:
    hauptbereich(w)
    lesbarkeit(w)
    fragen(w)
    belege(w)
    textwand(w)
    artikel(w)
