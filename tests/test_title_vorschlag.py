"""Title-Vorschlag wie im Titel-Check der Website (nextfix-site, assets/js/site.js)."""

import pytest

from app.onpage import abgleich
from app.onpage.abgleich import TITLE_MAX, gross, title_vorschlag


@pytest.mark.parametrize("keyword, title, erwartet", [
    # Füllteil „Home“ raus, Firmenname bleibt
    ("bäckerei hamburg", "Home | Bäckerei Sommer", "Bäckerei Hamburg | Bäckerei Sommer"),
    # Suchbegriff samt „für“ aus dem Rest, zu lang → nur der erste Gedanke
    ("Steuerberater Freiberufler", "Steuerberatung für Freiberufler und kleine Firmen | Kanzlei Okafor",
     "Steuerberater Freiberufler: Steuerberatung | Kanzlei Okafor"),
    ("ki agentur", "Radhaus – Digitale Lösungen", "KI Agentur: Digitale Lösungen | Radhaus"),
    # nur Füllteil: kein „SEO Check: Startseite“, kein leeres „SEO Check: |“
    ("seo check", "Startseite", "SEO Check"),
    ("on premise ki", "On-Premise KI vs. Cloud: Was ist besser für Unternehmen im Mittelstand? – Radhaus",
     "On Premise KI | Radhaus"),
    # kürzester Teil enthält den Suchbegriff → der andere kurze Teil ist der Name
    ("friseur kiel", "Startseite | Friseur in Kiel | Salon Haarscharf", "Friseur Kiel | Salon Haarscharf"),
    # „Willkommen bei“ weg
    ("fahrrad reparatur hamburg", "Willkommen bei Radhaus Elbe | Fahrräder, Reparatur und Zubehör in Hamburg seit 1998",
     "Fahrrad Reparatur Hamburg: Fahrräder | Radhaus Elbe"),
    ("zahnarzt altona",
     "Herzlich willkommen bei Zahnarztpraxis Dr. Weber – Ihr Zahnarzt in Hamburg-Altona für die ganze Familie",
     "Zahnarzt Altona | Zahnarztpraxis Dr. Weber"),
    # ohne Suchbegriff: nur aufräumen
    ("", "Home | Bäckerei Sommer", "Bäckerei Sommer"),
])
def test_title_vorschlag(keyword, title, erwartet):
    assert title_vorschlag(keyword, title) == erwartet


def test_nie_leere_teile():
    for keyword, title in [("seo check", ""), ("seo check", "Home"), ("seo check", "Home | Startseite"),
                           ("bäckerei", "Bäckerei | Bäckerei Sommer")]:
        v = title_vorschlag(keyword, title)
        assert v and ": |" not in v and not v.endswith((":", "|")) and "  " not in v


def test_zu_lang_wird_immer_gekuerzt():
    begriff = "sehr langer suchbegriff " * 5
    v = title_vorschlag(begriff, "Eine Seite | Firma")
    assert 0 < len(v) <= TITLE_MAX


def test_schreibweise():
    assert gross("ki beratung", "") == "KI Beratung"
    assert gross("seo für anfänger", "") == "SEO für Anfänger"          # Füllwort klein
    assert gross("iphone reparatur", "iPhone Reparatur in Kiel") == "iPhone Reparatur"   # wie im Titel


def test_kurzes_keywortwort_frisst_keine_laengeren_woerter():
    # „ki“ darf „Kiel“ nicht als Treffer werten
    assert title_vorschlag("ki beratung", "Beratung in Kiel | Radhaus") == "KI Beratung in Kiel | Radhaus"


def test_vorschlag_auch_bei_zu_langem_title():
    from app.onpage.seite import lesen
    lang = "SEO Check für kleine Firmen, Selbstständige und Vereine aus ganz Norddeutschland | Radhaus"
    html = f"<html><head><title>{lang}</title></head><body><h1>SEO Check</h1></body></html>"
    p = {x.id: x for x in abgleich.pruefen(lesen(html, "https://ex.de/"), "seo check")}
    assert p["title_keyword"].ok and not p["snippet_laenge"].ok
    assert p["snippet_laenge"].vorschlag == "SEO Check für kleine Firmen | Radhaus"
