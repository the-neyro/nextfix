import pytest

from app import config
from tests import testseite as ts


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Jeder Test bekommt eine eigene, leere Datenbank."""
    pfad = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PFAD", pfad)
    # Nie echte Schlüssel des Rechners benutzen (kein Abruf bei Open PageRank aus Tests)
    monkeypatch.setattr(config, "OPR_SCHLUESSEL", tmp_path / "kein-opr-schluessel.txt")
    return pfad


@pytest.fixture(scope="session")
def testseite():
    """Lokale Testseite, liefert die Basis-URL."""
    server, url = ts.starten()
    yield url
    server.shutdown()


# ---------- langsame Tests (z. B. der Prüfstand) nur mit --langsam ----------

def pytest_addoption(parser):
    parser.addoption("--langsam", action="store_true", help="auch langsame Tests ausführen (z. B. Prüfstand, ~1-2 Min.)")


def pytest_configure(config):
    config.addinivalue_line("markers", "langsam: langsamer Test, läuft nur mit --langsam")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--langsam"):
        return
    ueberspringen = pytest.mark.skip(reason="langsam: mit --langsam ausführen")
    for item in items:
        if "langsam" in item.keywords:
            item.add_marker(ueberspringen)
