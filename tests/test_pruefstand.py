"""Prüfstand (scripts/pruefstand.py): Soll für jede Prüfung und echter Crawl gegen die Test-Websites."""

import json

import pytest

from app.checks import REGISTER
from scripts import pruefstand


def test_jede_pruefung_hat_soll_oder_begruendung():
    soll = pruefstand.soll_liste()
    ja = {s.check for s in soll if s.ja}
    nein = {s.check for s in soll if not s.ja}
    unbekannt = ({s.check for s in soll} | set(pruefstand.NICHT_TESTBAR) | set(pruefstand.TEILWEISE)) - set(REGISTER)
    assert not unbekannt
    for c in set(REGISTER) - set(pruefstand.NICHT_TESTBAR):
        assert c in ja, f"{c}: kein Fall, bei dem die Prüfung anschlagen muss"
        assert c in nein or c in pruefstand.TEILWEISE, f"{c}: kein Grenzfall, bei dem sie nicht anschlagen darf"


def test_bekannte_abweichungen_haben_grund():
    for (art, check, ort), grund in pruefstand.BEKANNT.items():
        assert art in ("fehlalarm", "verpasst") and check in REGISTER and ort and grund


@pytest.mark.langsam
def test_pruefstand():
    """Echter Crawl aller Test-Websites. Eigene Datenbank (tmp, conftest), Crawls nacheinander."""
    e = pruefstand.ausfuehren(melden=lambda *_: None)
    assert not e.unerwartet(), "Neue Abweichungen:\n" + "\n".join(map(str, sorted(e.unerwartet())))
    assert not e.behoben(), "Behoben, aus BEKANNT streichen:\n" + "\n".join(map(str, sorted(e.behoben())))


def test_statischer_export(tmp_path):
    from scripts.pruefstand_web import export
    zahlen = export.schreiben(pruefstand.websites_bauen(), tmp_path)
    soll = json.loads((tmp_path / "soll.json").read_text())
    assert zahlen["soll"] == len(soll) == len(pruefstand.soll_liste())
    start = (tmp_path / "haupt" / "index.html").read_text()
    assert 'href="uebersicht/"' in start and "127.0.0.1" not in start   # relative Links
    weiter = next(s for s in soll if s["pfad"] == "/weiterleitung-301" and s["check"] == "perm_redirect")
    assert weiter["nur_lokal"] and not (tmp_path / "haupt" / "weiterleitung-301").exists()
    titel = next(s for s in soll if s["pfad"] == "/title-71")
    assert titel["nur_lokal"] is None and (tmp_path / "haupt" / "title-71" / "index.html").exists()
