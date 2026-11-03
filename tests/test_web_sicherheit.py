"""Browserzugriffe auf die lokale App absichern, ohne echte Daten anzufassen."""

import pytest
from fastapi.testclient import TestClient

from app.web import app


@pytest.mark.parametrize("host,status", [("evil.example", 400), ("localhost:8000", 200),
                                        ("127.0.0.1:8000", 200), ("testserver", 200)])
def test_nur_lokale_hosts(host, status):
    antwort = TestClient(app).get("/openapi.json", headers={"Host": host})
    assert antwort.status_code == status


@pytest.mark.parametrize("methode", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("headers", [
    {"Origin": "https://evil.example"}, {"Origin": "null"}, {"Origin": "http://["},
    {"Origin": "https://localhost.evil.example"}, {"Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "same-site"},
    {"Origin": "https://evil.example", "Sec-Fetch-Site": "same-origin"},
])
def test_fremde_aenderungen_abgelehnt(methode, headers):
    antwort = TestClient(app).request(methode, "/gibt-es-nicht", headers=headers)
    assert antwort.status_code == 403


@pytest.mark.parametrize("headers", [{}, {"Origin": "http://localhost:8000"},
    {"Origin": "http://127.0.0.1:8000"}, {"Sec-Fetch-Site": "same-origin"},
    {"Sec-Fetch-Site": "none"}])
def test_lokale_und_skript_aenderungen_bleiben_moeglich(headers):
    antwort = TestClient(app).post("/api/projekte", json={"domain": "example.de"}, headers=headers)
    assert antwort.status_code == 201


def test_fremdes_lesen_braucht_keinen_csrf_check():
    assert TestClient(app).get("/openapi.json", headers={"Origin": "https://evil.example"}).status_code == 200
