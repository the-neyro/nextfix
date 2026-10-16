"""Echte Quelle: Google Search Console API (Search Analytics) per Service-Account.

Ablauf: JWT mit dem privaten Schlüssel signieren → Access-Token holen →
pro Tag Search Analytics abfragen (Dimensionen date, query, page, country, device),
seitenweise je 25.000 Zeilen. Keine Google-Bibliothek nötig, nur httpx + PyJWT.

Einrichtung (Schlüssel, Zugriff in der Search Console): docs/anleitung-gsc.md
"""

import json
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
import jwt

from app import config
from app.gsc.fehler import GscFehler

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
BASIS = "https://www.googleapis.com/webmasters/v3"
DIMENSIONEN = ["date", "query", "page", "country", "device"]
ZEILEN_PRO_ANFRAGE = 25_000  # Maximum der API
PFLICHTFELDER = ("client_email", "private_key", "token_uri")


def schluessel_laden(pfad: Path | None = None) -> dict:
    """Liest die JSON-Datei des Service-Accounts und prüft die nötigen Felder."""
    pfad = Path(pfad or config.GSC_SCHLUESSEL)
    if not pfad.is_file():
        raise GscFehler(f"Kein Schlüssel gefunden: {pfad} (Einrichtung: docs/anleitung-gsc.md)")
    try:
        daten = json.loads(pfad.read_text())
    except (OSError, ValueError) as e:
        raise GscFehler(f"Schlüsseldatei nicht lesbar: {e}") from None
    if daten.get("type") != "service_account" or any(not daten.get(f) for f in PFLICHTFELDER):
        raise GscFehler("Schlüsseldatei ist kein Service-Account-Schlüssel (type, client_email, private_key, token_uri)")
    return daten


def _wurzel(domain: str) -> str:
    return domain.lower().removeprefix("www.")


class GscApiQuelle:
    name = "gsc"

    def __init__(self, schluessel: dict | None = None, client: httpx.Client | None = None):
        self._schluessel = schluessel
        self._client = client or httpx.Client(timeout=60)
        self._token: str | None = None
        self._token_bis = 0.0

    @property
    def schluessel(self) -> dict:
        if self._schluessel is None:
            self._schluessel = schluessel_laden()
        return self._schluessel

    # ---------- HTTP ----------

    def _token_holen(self) -> str:
        if self._token and time.time() < self._token_bis - 60:
            return self._token
        s = self.schluessel
        jetzt = int(time.time())
        try:
            behauptung = jwt.encode({"iss": s["client_email"], "scope": SCOPE, "aud": s["token_uri"],
                                     "iat": jetzt, "exp": jetzt + 3600}, s["private_key"], algorithm="RS256")
        except (ValueError, TypeError, jwt.PyJWTError) as e:
            raise GscFehler(f"Privater Schlüssel unbrauchbar: {e}") from None
        antwort = self._senden("POST", s["token_uri"], data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": behauptung})
        if antwort.status_code != 200:
            raise GscFehler(f"Anmeldung bei Google fehlgeschlagen ({antwort.status_code}): {_meldung(antwort)}")
        daten = antwort.json()
        self._token = daten["access_token"]
        self._token_bis = time.time() + int(daten.get("expires_in", 3600))
        return self._token

    def _senden(self, methode: str, url: str, **kwargs) -> httpx.Response:
        try:
            return self._client.request(methode, url, **kwargs)
        except httpx.HTTPError as e:
            raise GscFehler(f"Search Console nicht erreichbar: {e}") from None

    def _api(self, methode: str, pfad: str, json_daten: dict | None = None) -> dict:
        antwort = self._senden(methode, BASIS + pfad, json=json_daten,
                               headers={"Authorization": f"Bearer {self._token_holen()}"})
        if antwort.status_code == 403:
            raise GscFehler(f"Kein Zugriff ({_meldung(antwort)}). In der Search Console unter Einstellungen → "
                            f"Nutzer und Berechtigungen diese Adresse hinzufügen: {self.schluessel['client_email']}")
        if antwort.status_code == 429:
            raise GscFehler("Google-Kontingent erschöpft (429). Später erneut versuchen.")
        if antwort.status_code >= 400:
            raise GscFehler(f"Search-Console-API-Fehler {antwort.status_code}: {_meldung(antwort)}")
        return antwort.json()

    # ---------- Properties ----------

    def properties(self) -> list[dict]:
        """Alle Properties, auf die der Service-Account Zugriff hat."""
        eintraege = self._api("GET", "/sites").get("siteEntry", [])
        return sorted(({"property": e["siteUrl"], "berechtigung": e.get("permissionLevel", "")} for e in eintraege
                       if e.get("permissionLevel") != "siteUnverifiedUser"), key=lambda e: e["property"])

    def property_finden(self, domain: str) -> str:
        """Passende Property zur Domain: zuerst Domain-Property (sc-domain:), dann URL-Präfix mit gleichem Host."""
        vorhanden = [p["property"] for p in self.properties()]
        wurzel = _wurzel(domain)
        if f"sc-domain:{wurzel}" in vorhanden:
            return f"sc-domain:{wurzel}"
        praefixe = [p for p in vorhanden if not p.startswith("sc-domain:")
                    and _wurzel(urlparse(p).hostname or "") == wurzel]
        # https vor http, exakter Host vor www-Variante
        praefixe.sort(key=lambda p: (not p.startswith("https://"), urlparse(p).hostname != domain.lower(), p))
        if praefixe:
            return praefixe[0]
        liste = ", ".join(vorhanden) or "keine"
        raise GscFehler(f"Keine Property für {domain} freigegeben (sichtbar: {liste}). "
                        f"Service-Account in der Search Console hinzufügen: {self.schluessel['client_email']}")

    # ---------- Daten ----------

    def abrufen(self, domain: str, von: date, bis: date, property: str | None = None) -> list[dict]:
        prop = property or self.property_finden(domain)
        pfad = f"/sites/{quote(prop, safe='')}/searchAnalytics/query"
        zeilen = []
        tag = von
        while tag <= bis:  # pro Tag abfragen, damit das Tageslimit pro Anfrage nicht greift
            start = 0
            while True:
                antwort = self._api("POST", pfad, {
                    "startDate": tag.isoformat(), "endDate": tag.isoformat(), "dimensions": DIMENSIONEN,
                    "type": "web", "rowLimit": ZEILEN_PRO_ANFRAGE, "startRow": start})
                seite = antwort.get("rows", [])
                zeilen += [_umwandeln(z) for z in seite]
                if len(seite) < ZEILEN_PRO_ANFRAGE:
                    break
                start += ZEILEN_PRO_ANFRAGE
            tag += timedelta(days=1)
        return zeilen


def _umwandeln(z: dict) -> dict:
    datum, query, seite, land, geraet = z["keys"]
    return {"datum": datum, "query": query, "seite": seite, "land": land.lower(), "geraet": geraet.upper(),
            "klicks": int(z.get("clicks", 0)), "impressionen": int(z.get("impressions", 0)),
            "position": round(float(z.get("position", 0)), 1)}


def _meldung(antwort: httpx.Response) -> str:
    try:
        daten = antwort.json()
    except ValueError:
        return antwort.text[:200]
    fehler = daten.get("error")
    if isinstance(fehler, dict):
        return fehler.get("message", str(fehler))
    return str(daten.get("error_description") or fehler or daten)[:200]
