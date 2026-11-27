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


@pytest.mark.parametrize("methode,pfad,headers,status", [
    ("GET", "/openapi.json", {}, 200),
    ("GET", "/static/logo.svg", {}, 200),
    ("GET", "/fehlt", {}, 404),
    ("GET", "/openapi.json", {"Host": "evil.example"}, 400),
    ("POST", "/api/projekte", {"Origin": "https://evil.example"}, 403),
    ("POST", "/api/projekte", {}, 422),
    ("GET", "/", {}, 500),
])
def test_sicherheitsheader_auch_bei_fehlern(monkeypatch, methode, pfad, headers, status):
    from app.core import projekte

    def kaputt(*args):
        raise RuntimeError("Testfehler")
    if status == 500:
        monkeypatch.setattr(projekte, "liste", kaputt)
    antwort = TestClient(app, raise_server_exceptions=False).request(methode, pfad, headers=headers)
    assert antwort.status_code == status
    assert antwort.headers["X-Frame-Options"] == "DENY"
    assert antwort.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
    assert antwort.headers["X-Content-Type-Options"] == "nosniff"



def test_lifespan_typen_sind_aufloesbar():
    # Python 3.12 wertet diese Annotation schon beim Import aus, 3.14 erst bei Bedarf.
    from typing import get_type_hints
    from fastapi import FastAPI
    from app.web import lebenszyklus
    assert get_type_hints(lebenszyklus.__wrapped__)["_app"] is FastAPI
