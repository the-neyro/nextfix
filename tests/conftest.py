import pytest

from app import config
from tests import testseite as ts


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Jeder Test bekommt eine eigene, leere Datenbank."""
    pfad = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PFAD", pfad)
    return pfad


@pytest.fixture(scope="session")
def testseite():
    """Lokale Testseite, liefert die Basis-URL."""
    server, url = ts.starten()
    yield url
    server.shutdown()
