"""Vorher/Nachher-Beweis: die Demo-Website „Radhaus Elbe“ zweimal prüfen, einmal so wie sie ist und einmal mit den
behobenen ersten Aufgaben aus „Was jetzt tun“ (scripts/demo_website.py, Variante „nachher“).

Eigene Datenbank data/demo-vorher-nachher.db, data/seo.db bleibt unberührt, keine Anfragen an fremde Websites.
Start: .venv/bin/python -m scripts.vorher_nachher   → Zahlen auf der Konsole (Markdown)
"""

import os
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DB = WURZEL / "data" / "demo-vorher-nachher.db"

# Vor allen app-Importen: eigene Datenbank
os.environ["SEO_DB"] = str(DB)
for datei in DB.parent.glob(DB.name + "*"):
    datei.unlink()

from app.core import aufgaben, audit, projekte, teilnoten, vitals  # noqa: E402
from app.db import verbinden  # noqa: E402
from scripts import demo_website  # noqa: E402

# Wie scripts/screenshots.py: was nur am lokalen Demo-Server liegt (kein HTTPS, kein gzip, keine Cache-Header)
CHECKS_AUS = ["startseite_ohne_https", "http_nicht_auf_https", "kein_hsts", "unkomprimiert", "js_css_unkomprimiert",
              "js_css_ohne_cache"]


def pruefen(conn, name: str, nachher: bool) -> dict:
    server, basis = demo_website.starten(nachher=nachher)
    p = projekte.anlegen(conn, f"{name}.radhaus-elbe.de", f"Radhaus Elbe ({name})")
    audit.einstellungen_setzen(conn, p.id, start_url=basis, crawl_delay=0, quelle="beides", checks_aus=CHECKS_AUS)
    crawl = audit.crawl_starten(conn, p.id, warten=True)
    vitals.starten(conn, crawl["id"], anzahl=5, warten=True)
    audit.neu_auswerten(conn, crawl["id"])
    server.shutdown()
    return {"zustand": audit._health(conn, crawl["id"]),
            "seiten": conn.execute("SELECT COUNT(*) FROM seiten WHERE crawl_id=?", (crawl["id"],)).fetchone()[0],
            "noten": {n["name"]: n["wert"] for n in teilnoten.liste(conn, p.id, crawl["id"])},
            "aufgaben": aufgaben.liste(conn, crawl["id"])}


def _zahl(wert) -> str:
    return "–" if wert is None else f"{wert:g}" if isinstance(wert, (int, float)) else str(wert)


def _aufgaben(a: dict) -> list[str]:
    return [f"{i}. {x['was']} ({x['stufe']}, Wirkung {x['wirkung']})" for i, x in enumerate(a["aufgaben"], 1)] or ["keine"]


def main() -> None:
    conn = verbinden()
    vorher, nachher = pruefen(conn, "vorher", False), pruefen(conn, "nachher", True)
    print("| | Vorher | Nachher |\n|---|---|---|")
    print(f"| Website-Zustand | {_zahl(vorher['zustand'])} | {_zahl(nachher['zustand'])} |")
    print(f"| Geprüfte Seiten | {vorher['seiten']} | {nachher['seiten']} |")
    for name in vorher["noten"]:
        print(f"| {name} | {_zahl(vorher['noten'][name])} | {_zahl(nachher['noten'].get(name))} |")
    for titel, erg in (("Vorher", vorher), ("Nachher", nachher)):
        print(f"\n**Was jetzt tun – {titel}**\n")
        print("\n".join(_aufgaben(erg["aufgaben"])))
        print(f"\nFeinschliff: {len(erg['aufgaben']['feinschliff'])} Punkte")


if __name__ == "__main__":
    main()
