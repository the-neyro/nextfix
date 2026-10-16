"""Echte GSC-Quelle ohne Google: eigener RSA-Schlüssel + nachgebaute API (httpx.MockTransport)."""

import json
from datetime import date
from urllib.parse import parse_qs, unquote

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import config, gsc
from app.core import gsc_konto, positionen, projekte
from app.db import verbinden
from app.gsc import api

TOKEN_URI = "https://oauth2.googleapis.com/token"
EMAIL = "seo-tool@projekt.iam.gserviceaccount.com"


@pytest.fixture(scope="module")
def rsa_schluessel():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def schluessel(rsa_schluessel):
    pem = rsa_schluessel.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()).decode()
    return {"type": "service_account", "client_email": EMAIL, "private_key": pem, "token_uri": TOKEN_URI}


class FakeGoogle:
    """Nachbau der benötigten Endpunkte. Merkt sich alle Anfragen."""

    def __init__(self, public_key, sites=("sc-domain:ex.de",), zeilen_pro_tag=3, status=None):
        self.public_key = public_key
        self.sites = sites
        self.zeilen_pro_tag = zeilen_pro_tag
        self.status = status  # erzwungener Fehlerstatus für die API
        self.anfragen = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.anfragen.append(request)
        if str(request.url) == TOKEN_URI:
            form = parse_qs(request.content.decode())
            claims = jwt.decode(form["assertion"][0], self.public_key, algorithms=["RS256"], audience=TOKEN_URI)
            assert claims["iss"] == EMAIL and claims["scope"] == api.SCOPE
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer tok"
        if self.status:
            return httpx.Response(self.status, json={"error": {"message": "User does not have sufficient permission"}})
        if request.url.path.endswith("/sites"):
            return httpx.Response(200, json={"siteEntry": [
                {"siteUrl": s, "permissionLevel": "siteRestrictedUser"} for s in self.sites]})
        if request.url.path.endswith("/searchAnalytics/query"):
            body = json.loads(request.content)
            assert body["dimensions"] == api.DIMENSIONEN and body["startDate"] == body["endDate"]
            alle = [{"keys": [body["startDate"], f"begriff {i}", "https://ex.de/a", "DEU", "mobile"],
                     "clicks": 2, "impressions": 40, "ctr": 0.05, "position": 4.26}
                    for i in range(self.zeilen_pro_tag)]
            start = body["startRow"]
            return httpx.Response(200, json={"rows": alle[start:start + body["rowLimit"]]})
        return httpx.Response(404, json={"error": {"message": "unbekannt"}})


def quelle(schluessel, google) -> api.GscApiQuelle:
    return api.GscApiQuelle(schluessel, httpx.Client(transport=httpx.MockTransport(google)))


@pytest.fixture
def google(rsa_schluessel):
    return FakeGoogle(rsa_schluessel.public_key())


# ---------- Quelle ----------

def test_abrufen_mit_seitenweise_laden(schluessel, google, monkeypatch):
    monkeypatch.setattr(api, "ZEILEN_PRO_ANFRAGE", 2)  # 3 Zeilen pro Tag → 2 Anfragen pro Tag
    q = quelle(schluessel, google)
    zeilen = q.abrufen("ex.de", date(2026, 9, 1), date(2026, 9, 2))
    assert len(zeilen) == 6
    assert zeilen[0] == {"datum": "2026-09-01", "query": "begriff 0", "seite": "https://ex.de/a", "land": "deu",
                         "geraet": "MOBILE", "klicks": 2, "impressionen": 40, "position": 4.3}
    abfragen = [a for a in google.anfragen if a.url.path.endswith("/query")]
    assert len(abfragen) == 4
    assert unquote(abfragen[0].url.raw_path.decode()).count("sc-domain:ex.de") == 1
    # Token wird wiederverwendet: genau eine Anmeldung
    assert sum(str(a.url) == TOKEN_URI for a in google.anfragen) == 1


@pytest.mark.parametrize("sites, domain, erwartet", [
    (["sc-domain:ex.de", "https://ex.de/"], "www.ex.de", "sc-domain:ex.de"),
    (["http://ex.de/", "https://www.ex.de/", "https://ex.de/"], "ex.de", "https://ex.de/"),
    (["https://www.ex.de/", "https://anders.de/"], "ex.de", "https://www.ex.de/"),
])
def test_property_finden(schluessel, rsa_schluessel, sites, domain, erwartet):
    q = quelle(schluessel, FakeGoogle(rsa_schluessel.public_key(), sites=sites))
    assert q.property_finden(domain) == erwartet


def test_property_fehlt_nennt_adresse(schluessel, rsa_schluessel):
    q = quelle(schluessel, FakeGoogle(rsa_schluessel.public_key(), sites=["sc-domain:anders.de"]))
    with pytest.raises(gsc.GscFehler, match=f"anders.de.*{EMAIL}"):
        q.property_finden("ex.de")


def test_kein_zugriff_403(schluessel, rsa_schluessel):
    q = quelle(schluessel, FakeGoogle(rsa_schluessel.public_key(), status=403))
    with pytest.raises(gsc.GscFehler, match=f"Kein Zugriff.*sufficient permission.*{EMAIL}"):
        q.abrufen("ex.de", date(2026, 9, 1), date(2026, 9, 1), property="sc-domain:ex.de")


def test_anmeldung_abgelehnt(schluessel):
    q = quelle(schluessel, lambda r: httpx.Response(400, json={"error": "invalid_grant",
                                                               "error_description": "Invalid JWT Signature."}))
    with pytest.raises(gsc.GscFehler, match="Anmeldung.*Invalid JWT Signature"):
        q.properties()


def test_netzwerkfehler(schluessel):
    def kaputt(request):
        raise httpx.ConnectError("keine Verbindung")
    with pytest.raises(gsc.GscFehler, match="nicht erreichbar"):
        quelle(schluessel, kaputt).properties()


def test_schluessel_laden(tmp_path, schluessel):
    with pytest.raises(gsc.GscFehler, match="Kein Schlüssel gefunden"):
        api.schluessel_laden(tmp_path / "fehlt.json")
    (tmp_path / "kaputt.json").write_text("{nicht json")
    with pytest.raises(gsc.GscFehler, match="nicht lesbar"):
        api.schluessel_laden(tmp_path / "kaputt.json")
    (tmp_path / "falsch.json").write_text(json.dumps({"type": "authorized_user"}))
    with pytest.raises(gsc.GscFehler, match="kein Service-Account"):
        api.schluessel_laden(tmp_path / "falsch.json")
    (tmp_path / "gut.json").write_text(json.dumps(schluessel))
    assert api.schluessel_laden(tmp_path / "gut.json")["client_email"] == EMAIL


def test_kaputter_privater_schluessel(google, schluessel):
    with pytest.raises(gsc.GscFehler, match="Privater Schlüssel unbrauchbar"):
        quelle(dict(schluessel, private_key="kein pem"), google).properties()


# ---------- Projekt: Property, Status, Import ----------

@pytest.fixture
def mit_google(monkeypatch, tmp_path, schluessel, google):
    """Schlüsseldatei ablegen und die Quelle 'gsc' auf den Google-Nachbau umleiten."""
    pfad = tmp_path / "gsc-service-account.json"
    pfad.write_text(json.dumps(schluessel))
    monkeypatch.setattr(config, "GSC_SCHLUESSEL", pfad)
    monkeypatch.setitem(gsc.QUELLEN, "gsc", lambda: quelle(schluessel, google))
    return google


def test_property_setzen_formate():
    conn = verbinden()
    p = projekte.anlegen(conn, "ex.de").id
    assert gsc_konto.property_setzen(conn, p, " https://www.ex.de ") == "https://www.ex.de/"
    assert gsc_konto.property_setzen(conn, p, "sc-domain:ex.de") == "sc-domain:ex.de"
    assert gsc_konto.property_holen(conn, p) == "sc-domain:ex.de"
    assert gsc_konto.property_setzen(conn, p, "") is None and gsc_konto.property_holen(conn, p) is None
    with pytest.raises(gsc.GscFehler):
        gsc_konto.property_setzen(conn, p, "ex.de")


def test_status_ohne_schluessel(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GSC_SCHLUESSEL", tmp_path / "fehlt.json")
    conn = verbinden()
    p = projekte.anlegen(conn, "ex.de").id
    s = gsc_konto.status(conn, p)
    assert not s["schluessel_da"] and "Kein Schlüssel" in s["fehler"]
    with pytest.raises(positionen.PositionenFehler, match="Kein Schlüssel"):
        positionen.importieren(conn, p, "gsc", 3)


def test_import_ueber_gsc_merkt_property(mit_google):
    conn = verbinden()
    p = projekte.anlegen(conn, "www.ex.de").id
    assert gsc_konto.status(conn, p)["client_email"] == EMAIL
    r = positionen.importieren(conn, p, "gsc", 3, bis=date(2026, 10, 1))
    assert r == {"quelle": "gsc", "property": "sc-domain:ex.de", "von": "2026-09-29", "bis": "2026-10-01",
                 "zeilen": 9}
    assert gsc_konto.property_holen(conn, p) == "sc-domain:ex.de"
    assert positionen.bestand(conn, p)["quellen"] == ["gsc"]
    assert positionen.uebersicht(conn, p, tage=1)["kennzahlen"]["keywords"] == 3


def test_api_und_ui(mit_google):
    from app.web import app
    client = TestClient(app)
    p = client.post("/api/projekte", json={"domain": "ex.de"}).json()["id"]
    assert client.get(f"/api/projekte/{p}/gsc").json()["client_email"] == EMAIL
    t = client.post(f"/api/projekte/{p}/gsc/test").json()
    assert t["ok"] and t["passend"] == "sc-domain:ex.de"
    assert "passt zu diesem Projekt" in client.post(f"/projekte/{p}/gsc/test").text
    assert client.put(f"/api/projekte/{p}/gsc", json={"property": "quatsch"}).status_code == 400
    assert client.put(f"/api/projekte/{p}/gsc", json={"property": "https://ex.de"}).json()["property"] == "https://ex.de/"
    seite = client.get(f"/projekte/{p}/positionen").text
    assert EMAIL in seite and "Schlüssel gefunden" in seite
    assert client.post(f"/api/projekte/{p}/positionen/import", json={"quelle": "gsc", "tage": 2, "warten": True}).json()["zeilen"] == 6
