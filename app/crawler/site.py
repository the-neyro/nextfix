"""Fakten über die ganze Website: HTTPS-Weiterleitung, www-Auflösung, TLS-Zertifikat, llms.txt.

Ergebnis ist ein JSON-fähiges dict, das in crawls.fakten gespeichert wird.
Jeder Teil fängt seine Fehler selbst ab, damit ein Problem nicht den ganzen Crawl stoppt.
"""

import ipaddress
import re
import socket
import ssl
import warnings
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import httpx

ZERTIFIKAT_WARNUNG_TAGE = 30
LLMS_MAX_LINKS = 300


def sammeln(client: httpx.Client, start_url: str) -> dict:
    teile = urlsplit(start_url)
    host = teile.hostname or ""
    fakten: dict = {"llms": _llms(client, f"{teile.scheme}://{teile.netloc}")}
    if _ist_ip_oder_lokal(host):
        return fakten  # www-Varianten und Zertifikate ergeben bei IPs/localhost keinen Sinn
    haupt_ziel = _endziel(client, start_url)
    fakten["www"] = _www(client, teile, haupt_ziel)
    if teile.scheme == "https":
        fakten["http_zu_https"] = _http_zu_https(client, teile)
        fakten["tls"] = tls_pruefen(host, teile.port or 443)
    return fakten


def _ist_ip_oder_lokal(host: str) -> bool:
    if host in ("localhost", "") or host.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _endziel(client: httpx.Client, url: str) -> dict:
    """Folgt Weiterleitungen und liefert Endziel + Kette."""
    try:
        r = client.get(url, follow_redirects=True)
    except httpx.HTTPError as fehler:
        return {"url": url, "fehler": f"{type(fehler).__name__}: {fehler}"[:200]}
    kette = [f"{h.status_code} {h.url}" for h in r.history]
    return {"url": str(r.url), "status": r.status_code, "kette": kette}


def _http_zu_https(client: httpx.Client, teile) -> dict:
    http_url = f"http://{teile.netloc}/"
    ziel = _endziel(client, http_url)
    ziel["start"] = http_url
    ziel["ok"] = ziel.get("url", "").startswith("https://") if "fehler" not in ziel else True
    return ziel


def _www(client: httpx.Client, teile, haupt_ziel: dict) -> dict:
    """Andere Variante (mit/ohne www.) muss auf denselben Host umleiten wie die Hauptvariante."""
    host = teile.hostname
    andere = host[4:] if host.startswith("www.") else "www." + host
    port = f":{teile.port}" if teile.port else ""
    ziel = _endziel(client, f"{teile.scheme}://{andere}{port}/")
    ziel["start"] = f"{teile.scheme}://{andere}{port}/"
    if "fehler" in ziel or "fehler" in haupt_ziel:
        ziel["ok"] = True  # Variante existiert nicht (z. B. kein DNS): kein Doppel-Inhalt
    else:
        ziel["ok"] = urlsplit(ziel["url"]).hostname == urlsplit(haupt_ziel["url"]).hostname
    ziel["haupt"] = haupt_ziel.get("url")
    return ziel


def _llms(client: httpx.Client, wurzel: str) -> dict:
    """llms.txt: Markdown-Datei, die mit einer H1-Zeile ('# Name') beginnen soll."""
    try:
        r = client.get(wurzel + "/llms.txt", follow_redirects=True)
    except httpx.HTTPError:
        return {"status": None}
    ergebnis = {"status": r.status_code}
    if r.status_code == 200:
        ergebnis.update(llms_auswerten(r.text, str(r.url)))
    return ergebnis


def llms_auswerten(text: str, basis: str) -> dict:
    """Aufbau nach llmstxt.org: H1, Zitat mit Kurzbeschreibung, H2-Abschnitte mit Linklisten."""
    text = text.removeprefix("\ufeff")   # BOM am Dateianfang (Windows-Editoren)
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    # Markdown-Links [Titel](URL) und – oft in der Praxis – nackte URLs
    markdown = [urljoin(basis, l) for l in re.findall(r"\]\(([^)\s]+)", text)]
    nackt = [u.rstrip(".,;:") for u in re.findall(r"(?<!\()https?://[^\s)<>\]]+", text)]
    links = list(dict.fromkeys(markdown + nackt))
    return {
        "format_ok": bool(zeilen) and zeilen[0].startswith("# "),
        "zusammenfassung": any(z.startswith(">") for z in zeilen),
        "abschnitte": sum(z.startswith("## ") for z in zeilen),
        "links": links[:LLMS_MAX_LINKS],
        "links_anzahl": len(links),
    }


# ---------- TLS ----------

def tls_pruefen(host: str, port: int = 443, timeout: float = 10.0) -> dict:
    ergebnis: dict = {}
    try:
        kontext = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as roh:
            with kontext.wrap_socket(roh, server_hostname=host) as tls:
                zertifikat = tls.getpeercert()
                ergebnis["protokoll"] = tls.version()
        ergebnis.update(zertifikat_bewerten(zertifikat["notAfter"]))
        ergebnis["name_ok"] = True
    except ssl.SSLCertVerificationError as fehler:
        ergebnis["fehler"] = fehler.verify_message
        ergebnis["abgelaufen"] = fehler.verify_code == 10
        ergebnis["name_ok"] = fehler.verify_code != 62
    except (OSError, ssl.SSLError) as fehler:
        ergebnis["fehler"] = f"{type(fehler).__name__}: {fehler}"[:200]
    ergebnis["alt_erlaubt"] = _altes_tls_erlaubt(host, port, timeout)
    return ergebnis


def zertifikat_bewerten(not_after: str, jetzt: datetime | None = None) -> dict:
    """notAfter z. B. 'Jun  1 12:00:00 2027 GMT' → Ablaufdatum und Resttage."""
    ablauf = datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), tz=timezone.utc)
    jetzt = jetzt or datetime.now(timezone.utc)
    tage = (ablauf - jetzt).days
    return {"ablauf": ablauf.date().isoformat(), "rest_tage": tage, "abgelaufen": tage < 0}


def _altes_tls_erlaubt(host: str, port: int, timeout: float) -> bool | None:
    """Akzeptiert der Server noch TLS 1.0/1.1? None = nicht prüfbar (lokal nicht unterstützt, Netzfehler)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            kontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            kontext.check_hostname = False
            kontext.verify_mode = ssl.CERT_NONE
            kontext.minimum_version = ssl.TLSVersion.TLSv1
            kontext.maximum_version = ssl.TLSVersion.TLSv1_1
            kontext.set_ciphers("DEFAULT:@SECLEVEL=0")
    except (ValueError, ssl.SSLError):
        return None
    try:
        with socket.create_connection((host, port), timeout=timeout) as roh:
            with kontext.wrap_socket(roh, server_hostname=host):
                return True
    except ssl.SSLError:
        return False  # Server lehnt altes Protokoll ab
    except OSError:
        return None
