import pytest

from app.core import projekte
from app.db import verbinden


@pytest.mark.parametrize(
    "eingabe, erwartet",
    [
        ("example.de", "example.de"),
        ("https://WWW.Example.de/pfad?x=1", "www.example.de"),
        ("  shop.example.com/  ", "shop.example.com"),
    ],
)
def test_domain_normalisieren(eingabe, erwartet):
    assert projekte.domain_normalisieren(eingabe) == erwartet


@pytest.mark.parametrize("eingabe", ["", "   ", "localhost", "http://"])
def test_domain_ungueltig(eingabe):
    with pytest.raises(projekte.ProjektFehler):
        projekte.domain_normalisieren(eingabe)


def test_anlegen_liste_loeschen():
    conn = verbinden()
    p = projekte.anlegen(conn, "https://example.de")
    assert p.name == "example.de"
    assert [x.domain for x in projekte.liste(conn)] == ["example.de"]

    projekte.loeschen(conn, p.id)
    assert projekte.liste(conn) == []


def test_doppelte_domain():
    conn = verbinden()
    projekte.anlegen(conn, "example.de")
    with pytest.raises(projekte.ProjektFehler, match="existiert schon"):
        projekte.anlegen(conn, "https://example.de/")
