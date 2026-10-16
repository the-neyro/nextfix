"""Open PageRank: Autorität einer Domain (0–10), berechnet aus dem Link-Graphen von Common Crawl.

Kostenloser Schlüssel (30 000 Domains/Monat) unter openpagerank.keywordseverywhere.com, gespeichert in
~/.config/seo-tool/openpagerank-api-key.txt. Die Daten werden etwa monatlich aktualisiert.
Liefert nur einen Wert je Domain, keine einzelnen Links.
"""

import re
from pathlib import Path

import httpx

from app import config

BASIS = "https://openpagerank.keywordseverywhere.com/api/v1.0/getPageRank"
JE_ANFRAGE = 100   # Obergrenze der API


class OprFehler(RuntimeError):
    """Schlüssel fehlt/ungültig oder API nicht erreichbar."""


def schluessel_laden(pfad: Path | None = None) -> str:
    pfad = Path(pfad or config.OPR_SCHLUESSEL)
    if not pfad.is_file():
        raise OprFehler(f"Kein Open-PageRank-Schlüssel gefunden: {pfad}")
    schluessel = pfad.read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", schluessel):
        raise OprFehler("Schlüsseldatei für Open PageRank enthält keinen gültigen Schlüssel")
    return schluessel


def abfragen(domains: list[str], schluessel: str | None = None, client: httpx.Client | None = None) -> dict[str, dict]:
    """domain → {"wert": 0–10 | None, "rang": int | None, "stand": str | None, "fehler": str | None}."""
    schluessel = schluessel or schluessel_laden()
    client = client or httpx.Client(timeout=20)
    ergebnis = {}
    for i in range(0, len(domains), JE_ANFRAGE):
        try:
            r = client.get(BASIS, params={"domains[]": domains[i:i + JE_ANFRAGE]}, headers={"API-OPR": schluessel})
            daten = r.json()
        except (httpx.HTTPError, ValueError) as fehler:
            raise OprFehler(f"Open PageRank nicht erreichbar: {type(fehler).__name__}") from fehler
        if r.status_code != 200 or daten.get("status_code") != 200:
            raise OprFehler(f"Open PageRank: {daten.get('error') or r.status_code}")
        for z in daten.get("response", []):
            gefunden = z.get("status_code") == 200
            ergebnis[z["domain"]] = {
                "wert": float(z["page_rank_decimal"]) if gefunden else None,
                "rang": int(z["rank"]) if gefunden and z.get("rank") else None,
                "stand": daten.get("last_updated"),
                "fehler": None if gefunden else (z.get("error") or "nicht gefunden"),
            }
    return ergebnis
