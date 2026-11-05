"""Eingaben für Domain, Exportnamen und PDF-Fußzeilen bleiben reine Daten."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app import berichte, mcp_server
from app.core import projekte, positionen


@pytest.mark.parametrize("domain", ['a.de<img src=x>', 'a.de"test', "a.de space", "a.de;test"])
def test_domain_mit_html_oder_sonderzeichen_abgelehnt(domain):
    with pytest.raises(projekte.ProjektFehler):
        projekte.domain_normalisieren(domain)


def test_umlaut_domain_wird_idna_normalisiert():
    assert projekte.domain_normalisieren("https://bäcker.de/pfad") == "xn--bcker-gra.de"


@pytest.mark.parametrize("land", ["../deu", "deu/../../x", "<deu>", "de", "deuu", "dèu"])
def test_land_ist_kein_pfad_oder_html(monkeypatch, land):
    with pytest.raises(positionen.PositionenFehler):
        positionen._filter(land, None)
    # Auch am Dateinamen-Einstieg vor dem Export prüfen.
    monkeypatch.setattr(mcp_server.export, "keywords_csv", lambda *a, **k: pytest.fail("Export vor Prüfung"))
    with pytest.raises(positionen.PositionenFehler):
        mcp_server.keywords_csv(1, land=land)


def test_pdf_fusszeile_maskiert_html(monkeypatch):
    import playwright.sync_api
    gesehen = {}
    class Seite:
        def set_content(self, *args, **kwargs):
            pass
        def pdf(self, **kwargs):
            gesehen.update(kwargs)
            return b"%PDF-test"
    browser = SimpleNamespace(new_page=lambda: Seite(), close=lambda: None)
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", lambda: nullcontext(
        SimpleNamespace(chromium=SimpleNamespace(launch=lambda: browser))))
    assert berichte.html_zu_pdf("<p>Test</p>", '<img src=x> & "Titel"') == b"%PDF-test"
    assert '<img src=x>' not in gesehen["footer_template"]
    assert '&lt;img src=x&gt; &amp; &quot;Titel&quot;' in gesehen["footer_template"]
