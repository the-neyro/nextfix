"""Browserzugriffe auf die lokale App absichern, ohne echte Daten anzufassen."""

import pytest
from fastapi.testclient import TestClient

from app.web import app


@pytest.mark.parametrize("host,status", [("evil.example", 400), ("localhost:8000", 200),
                                        ("127.0.0.1:8000", 200), ("testserver", 200)])
def test_nur_lokale_hosts(host, status):
    antwort = TestClient(app).get("/openapi.json", headers={"Host": host})
    assert antwort.status_code == status
