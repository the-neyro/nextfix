"""Prüfstand: Erkennt Nextfix jede Prüfung richtig? Lokale Test-Websites mit bekannter Wahrheit
(scripts/pruefstand_web/), echter Crawl mit dem Nextfix-Code, Vergleich Soll/Ist, Tabelle als Markdown.

Start:  .venv/bin/python -m scripts.pruefstand [--bericht datei.md] [--ohne-browser] [--export ordner]
Eigene Datenbank data/pruefstand.db (data/seo.db bleibt unberührt), keine Anfragen ins Internet.
Exit-Code 1, wenn es Abweichungen gibt, die nicht in BEKANNT stehen (oder dort stehen, aber behoben sind).
"""

import argparse
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.pruefstand_web import Antwort, Soll, Website, haupt, weitere

# Was lokal nicht nachstellbar ist: Prüfung → Begründung. Nextfix überspringt www/HTTPS/TLS bei localhost und IPs
# absichtlich (app/crawler/site.py), echte Zertifikate brauchen einen echten Hostnamen.
NICHT_TESTBAR = {
    "mixed_content": "braucht eine HTTPS-Seite; lokal läuft alles über http://",
    "https_verlinkt_http": "braucht eine HTTPS-Seite",
    "kein_hsts": "Header wird nur auf HTTPS-Seiten bewertet",
    "sitemap_http_bei_https": "braucht eine HTTPS-Startadresse",
    "http_nicht_auf_https": "braucht HTTPS und einen echten Hostnamen (Nextfix prüft bei localhost/IP nicht)",
    "www_aufloesung": "braucht einen echten Hostnamen mit www-Variante (DNS)",
    "zertifikat_ablauf": "braucht ein echtes TLS-Zertifikat",
    "zertifikat_name": "braucht ein echtes TLS-Zertifikat",
    "tls_veraltet": "braucht einen TLS-Server mit TLS 1.0/1.1",
}
# Teilweise testbar: nur eine Richtung lässt sich lokal nachstellen
TEILWEISE = {
    "startseite_ohne_https": "nur „schlägt an“; der Fall „HTTPS-Startseite“ braucht HTTPS",
    "passwort_ohne_https": "nur auf http://; dieselbe Seite über HTTPS braucht HTTPS",
    "ohne_last_modified": "nur ganze Website; Grenzfall „alle Seiten mit Header“ auf Website sauber",
}
BROWSER_WEBSITES = {"js", "tempo"}
BROWSER_CHECKS = {"inhalt_nur_per_js", "ladezeit_lcp", "ladezeit_cls", "ladezeit_tbt"}

# Bekannte Abweichungen (bewusst noch nicht behoben), Schlüssel aus Ergebnis.abweichungen(): Grund
NICHT_ABGERUFEN = "Crawler ruft Ziele von Canonical, hreflang und llms.txt nicht selbst ab, nur verlinkte Seiten"
BEKANNT: dict[tuple[str, str, str], str] = {
    ("verpasst", "canonical_defekt", "haupt:/canonical-auf-nie-verlinkt"): NICHT_ABGERUFEN,
    ("verpasst", "hreflang_ziel_defekt", "haupt:/hl/ziel-nie-verlinkt"): NICHT_ABGERUFEN,
    ("verpasst", "llms_tote_links", "haupt:* (/llms-nie-verlinkt-404)"): NICHT_ABGERUFEN,
    ("verpasst", "hreflang_code_ungueltig", "haupt:/hl/code-en-uk"):
        "Regionscode wird nur auf Form geprüft (2 Buchstaben), nicht gegen die ISO-3166-Liste",
}


# ---------- Server ----------

class _Handler(BaseHTTPRequestHandler):
    website: Website

    def _antworten(self, mit_body: bool) -> None:
        a = self.website.finden(self.path) or Antwort(status=404, body="<h1>Seite nicht gefunden</h1>")
        if a.abbrechen:
            self.close_connection = True
            return
        if mit_body and a.verzoegerung:
            time.sleep(a.verzoegerung)
        daten, header = a.daten("gzip" in (self.headers.get("Accept-Encoding") or ""))
        self.send_response(a.status)
        for k, v in header.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(daten)))
        self.end_headers()
        if mit_body:
            self.wfile.write(daten)

    def do_GET(self):
        self._antworten(True)

    def do_HEAD(self):
        self._antworten(False)

    def log_message(self, *args):
        pass


class _FremdHandler(_Handler):
    """„Fremde“ Website für externe Links: /ok/* gibt es, /umleitung leitet dorthin, /nur-get lehnt HEAD ab."""

    def _antworten(self, mit_body: bool) -> None:
        pfad = self.path.split("?")[0]
        if pfad.startswith("/ok/"):
            a = Antwort(body="<p>ok</p>")
        elif pfad == "/umleitung":
            a = Antwort(status=301, header={"Location": "/ok/ziel"}, typ=None)
        elif pfad == "/nur-get":
            a = Antwort(body="<p>ok</p>") if mit_body else Antwort(status=405, typ=None)
        else:
            a = Antwort(status=404, body="<p>weg</p>")
        daten, header = a.daten(False)
        self.send_response(a.status)
        for k, v in header.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(daten)))
        self.end_headers()
        if mit_body:
            self.wfile.write(daten)


def _server(handler: type, host: str = "127.0.0.1") -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://{host}:{server.server_port}/"


BAUPLAENE = {"haupt": haupt.bauen, "sauber": weitere.sauber, "leer": weitere.leer, "kaputt": weitere.kaputt,
             "riesig": weitere.riesig, "js": weitere.js, "tempo": weitere.tempo}


def websites_bauen(basis: dict[str, str] | None = None, fremd: str = "http://localhost:1") -> dict[str, Website]:
    """Alle Websites mit Soll. Ohne basis: Platzhalter-Adressen (für Tests, die nur das Soll brauchen)."""
    basis = basis or {name: f"http://127.0.0.1:{1000 + i}/" for i, name in enumerate(BAUPLAENE)}
    return {name: plan(Website(name, basis[name], fremd)) for name, plan in BAUPLAENE.items() if name in basis}


def soll_liste(websites: dict[str, Website] | None = None) -> list[Soll]:
    return [s for w in (websites or websites_bauen()).values() for s in w.soll]


# ---------- Vergleich ----------

@dataclass
class Treffer:
    check: str
    website: str
    pfad: str | None   # None = ganze Website
    detail: str

    @property
    def ort(self) -> str:
        return f"{self.website}:{self.pfad}" if self.pfad else f"{self.website}:* ({self.detail})"


@dataclass
class Zeile:
    check: str
    richtig: list[Soll] = field(default_factory=list)
    verpasst: list[Soll] = field(default_factory=list)
    fehlalarme: list[str] = field(default_factory=list)   # Orte
    soll_anzahl: int = 0


def _passt(s: Soll, t: Treffer) -> bool:
    if s.check != t.check or s.website != t.website:
        return False
    if s.pfad is not None:
        return t.pfad == s.pfad
    return t.pfad is None and (s.nadel is None or s.nadel in t.detail)


def vergleichen(soll: list[Soll], treffer: list[Treffer], checks: list[str]) -> dict[str, Zeile]:
    zeilen = {c: Zeile(c) for c in checks}
    for s in soll:
        z = zeilen[s.check]
        z.soll_anzahl += 1
        gefunden = [t for t in treffer if _passt(s, t)]
        if s.ja and gefunden or not s.ja and not gefunden:
            z.richtig.append(s)
        elif s.ja:
            z.verpasst.append(s)
        else:
            z.fehlalarme.append(s.ort)
    erwartet_ja = [s for s in soll if s.ja]
    for t in treffer:   # streng: jeder Treffer muss als „ja“ erwartet sein
        if not any(_passt(s, t) for s in erwartet_ja) and t.ort not in zeilen[t.check].fehlalarme:
            if not any(_passt(s, t) for s in soll):   # „nein“-Treffer stehen schon oben
                zeilen[t.check].fehlalarme.append(t.ort)
    return zeilen


@dataclass
class Ergebnis:
    zeilen: dict[str, Zeile]
    ohne_browser: bool
    dauer_s: float

    def abweichungen(self) -> set[tuple[str, str, str]]:
        """(Art, Prüfung, Ort) für alle Fehlalarme und verpassten Fälle."""
        menge = set()
        for z in self.zeilen.values():
            menge |= {("fehlalarm", z.check, ort) for ort in z.fehlalarme}
            menge |= {("verpasst", z.check, s.ort) for s in z.verpasst}
        return menge

    def unerwartet(self) -> set[tuple[str, str, str]]:
        return self.abweichungen() - set(BEKANNT)

    def behoben(self) -> set[tuple[str, str, str]]:
        """Bekannte Abweichungen, die nicht mehr auftreten (dann aus BEKANNT streichen)."""
        geprueft = {k for k in BEKANNT if not (self.ohne_browser and k[1] in BROWSER_CHECKS)}
        return geprueft - self.abweichungen()


# ---------- Ablauf ----------

def browser_verfuegbar() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch().close()
        return True
    except Exception:
        return False


def _treffer_lesen(conn, crawl_id: int, w: Website) -> list[Treffer]:
    zeilen = conn.execute("SELECT i.check_id, s.url, COALESCE(i.detail, '') FROM issues i "
                          "LEFT JOIN seiten s ON s.id = i.seite_id WHERE i.crawl_id=?", (crawl_id,)).fetchall()
    wurzel = w.basis.rstrip("/")
    return [Treffer(c, w.name, url[len(wurzel):] if url else None,
                    detail.replace(wurzel, "").replace(w.fremd, "<fremd>")) for c, url, detail in zeilen]


def ausfuehren(mit_browser: bool | None = None, melden=print) -> Ergebnis:
    """Server starten, alle Websites crawlen (Datenbank: app.config.DB_PFAD), Soll und Ist vergleichen."""
    from app import checks
    from app.core import audit, projekte, vitals
    from app.db import verbinden

    t0 = time.perf_counter()
    if mit_browser is None:
        mit_browser = browser_verfuegbar()
    namen = [n for n in BAUPLAENE if mit_browser or n not in BROWSER_WEBSITES]
    fremd_server, fremd = _server(_FremdHandler, host="localhost")
    server = {n: _server(type(f"Handler_{n}", (_Handler,), {}))[0] for n in namen}
    basis = {n: f"http://127.0.0.1:{s.server_port}/" for n, s in server.items()}
    websites = websites_bauen(basis, fremd.rstrip("/"))
    for n, s in server.items():
        s.RequestHandlerClass.website = websites[n]

    treffer: list[Treffer] = []
    conn = verbinden()
    try:
        for n in namen:
            w = websites[n]
            p = projekte.anlegen(conn, f"{n}.pruefstand.test", f"Prüfstand {n}")
            audit.einstellungen_setzen(conn, p.id, start_url=w.basis, crawl_delay=0, seitenlimit=1000,
                                       js_rendern=n == "js")
            crawl = audit.crawl_starten(conn, p.id, warten=True)
            if n == "tempo":
                vitals.starten(conn, crawl["id"], anzahl=10, geraete=("mobile",), warten=True)
            status = audit.crawl_holen(conn, crawl["id"])
            if status["status"] != "fertig":
                raise RuntimeError(f"Crawl {n}: {status['status']} {status['fehler_text']}")
            neu = _treffer_lesen(conn, crawl["id"], w)
            treffer += neu
            melden(f"{n}: {status['seiten_anzahl']} Seiten, {len(neu)} Treffer")
    finally:
        conn.close()
        for s in [*server.values(), fremd_server]:
            s.shutdown()

    soll = [s for s in soll_liste(websites)]
    zeilen = vergleichen(soll, treffer, list(checks.REGISTER))
    return Ergebnis(zeilen, not mit_browser, time.perf_counter() - t0)


# ---------- Tabelle ----------

def tabelle(e: Ergebnis) -> str:
    def orte(liste: list[str]) -> str:
        return "<br>".join(f"`{o}`" for o in liste) or "–"
    kopf = ["| Prüfung | richtig erkannt | Fehlalarme (URL) | verpasst (URL) | nicht testbar |", "|---|---|---|---|---|"]
    zeilen = []
    for c, z in sorted(e.zeilen.items()):
        if e.ohne_browser and c in BROWSER_CHECKS:
            testbar = "nicht geprüft: Chromium fehlt"
        else:
            testbar = NICHT_TESTBAR.get(c) or TEILWEISE.get(c) or ""
        richtig = f"{len(z.richtig)}/{z.soll_anzahl}" if z.soll_anzahl else "–"
        zeilen.append(f"| `{c}` | {richtig} | {orte(z.fehlalarme)} | {orte([s.ort for s in z.verpasst])} | {testbar} |")
    return "\n".join(kopf + zeilen)


def main() -> int:
    from app import config

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bericht", type=Path, help="Tabelle als Markdown in diese Datei schreiben")
    parser.add_argument("--ohne-browser", action="store_true", help="JS-Rendering und Ladezeit auslassen")
    parser.add_argument("--export", type=Path, help="Websites als statische HTML-Dateien in diesen Ordner schreiben")
    args = parser.parse_args()
    if args.export:
        from scripts.pruefstand_web import export
        export.schreiben(websites_bauen(), args.export)
        print(f"Export: {args.export}")
        return 0

    db = config.PROJEKT_ROOT / "data" / "pruefstand.db"
    for alt in db.parent.glob(db.name + "*"):
        alt.unlink()
    config.DB_PFAD = db
    config.OPR_SCHLUESSEL = db.parent / "kein-opr-schluessel"   # keine Abfrage bei Open PageRank
    e = ausfuehren(mit_browser=False if args.ohne_browser else None)
    text = tabelle(e)
    if args.bericht:
        args.bericht.parent.mkdir(parents=True, exist_ok=True)
        args.bericht.write_text(text + "\n")
    else:
        print(text)
    neu, behoben = e.unerwartet(), e.behoben()
    print(f"\n{len(e.abweichungen())} Abweichungen, davon {len(neu)} neu, {len(behoben)} bekannte behoben "
          f"({e.dauer_s:.0f} s)")
    for a in sorted(neu):
        print("NEU", *a)
    for a in sorted(behoben):
        print("BEHOBEN", *a)
    return 1 if neu or behoben else 0


if __name__ == "__main__":
    sys.exit(main())
