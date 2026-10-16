"""Zentrale Einstellungen."""

import os
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent

# Pfad zur SQLite-Datei, per Umgebungsvariable überschreibbar (z. B. für Tests)
DB_PFAD = Path(os.environ.get("SEO_DB", PROJEKT_ROOT / "data" / "seo.db"))

# Service-Account-Schlüssel (JSON) für die Google Search Console. Liegt bewusst außerhalb
# des Projekts, damit er nie ins Git gerät. Einrichtung: docs/anleitung-gsc.md
GSC_SCHLUESSEL = Path(os.environ.get("SEO_GSC_SCHLUESSEL",
                                     Path.home() / ".config" / "seo-tool" / "gsc-service-account.json"))

# API-Schlüssel für Bing Webmaster Tools (Textdatei mit nur dem Schlüssel), ebenfalls außerhalb des Repos.
BING_SCHLUESSEL = Path(os.environ.get("SEO_BING_SCHLUESSEL",
                                      Path.home() / ".config" / "seo-tool" / "bing-api-key.txt"))

# API-Schlüssel für Open PageRank (Domain-Autorität, kostenlos 30 000 Domains/Monat), außerhalb des Repos.
OPR_SCHLUESSEL = Path(os.environ.get("SEO_OPR_SCHLUESSEL",
                                     Path.home() / ".config" / "seo-tool" / "openpagerank-api-key.txt"))
