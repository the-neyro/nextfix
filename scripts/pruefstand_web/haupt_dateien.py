"""Hauptwebsite, Teil JS- und CSS-Dateien: Größe, Anzahl, Kompression, Caching, Minifizierung, Blockieren."""

from scripts.pruefstand_web import Website

JS = "application/javascript"


def _lesbar(bytes_ziel: int) -> str:
    """Eingerücktes JavaScript mit genau `bytes_ziel` Bytes (nicht minifiziert)."""
    block = "function rechne(a, b) {\n    // Summe bilden\n    return a + b;\n}\n"
    text = block * (bytes_ziel // len(block) + 1)
    return text[:bytes_ziel]


def _einzeilig(bytes_ziel: int) -> str:
    """Minifiziertes JavaScript (eine Zeile) mit genau `bytes_ziel` Bytes."""
    kopf, fuss = "var d='", "';"
    return kopf + "x" * (bytes_ziel - len(kopf) - len(fuss)) + fuss


def _mit_skript(w: Website, pfad: str, datei: str, **kw) -> None:
    w.seite(pfad, nach_main=f'<script src="{datei}"></script>', **kw)


def alles(w: Website) -> None:
    w.datei("/js/2-1mb.js", _einzeilig(2_100_000), JS)
    w.datei("/js/1-9mb.js", _einzeilig(1_900_000), JS)
    _mit_skript(w, "/js-2-1mb", "/js/2-1mb.js", ja=["js_css_zu_gross"])
    _mit_skript(w, "/js-1-9mb", "/js/1-9mb.js", nein=["js_css_zu_gross"])

    for i in range(1, 101):
        w.datei(f"/css/datei-{i:03d}.css", f".k{i}{{margin:{i}px}}", "text/css")
    # + /stil.css auf jeder Seite = 101 bzw. 100 Dateien
    for pfad, anzahl, soll in (("/css-101", 100, "ja"), ("/css-100", 99, "nein")):
        links = "".join(f'<link rel="stylesheet" href="/css/datei-{i:03d}.css">' for i in range(1, anzahl + 1))
        w.seite(pfad, kopf=links, **{soll: ["zu_viele_js_css"]})

    w.datei("/js/ungezippt-1025.js", _einzeilig(1025), JS, gzip=False)
    w.datei("/js/ungezippt-1024.js", _einzeilig(1024), JS, gzip=False)
    _mit_skript(w, "/js-ungezippt-1025", "/js/ungezippt-1025.js", ja=["js_css_unkomprimiert"])
    _mit_skript(w, "/js-ungezippt-1024", "/js/ungezippt-1024.js", nein=["js_css_unkomprimiert"],
                warum={"js_css_unkomprimiert": "bis 1 KB lohnt Kompression kaum"})

    w.datei("/js/ohne-cache.js", "var a=1;", JS, header={})
    w.datei("/js/max-age-0.js", "var b=1;", JS, header={"Cache-Control": "max-age=0"})
    w.datei("/js/expires.js", "var c=1;", JS, header={"Expires": "Thu, 31 Dec 2037 23:55:55 GMT"})
    w.datei("/js/max-age.js", "var e=1;", JS)
    _mit_skript(w, "/js-ohne-cache", "/js/ohne-cache.js", ja=["js_css_ohne_cache"])
    _mit_skript(w, "/js-max-age-0", "/js/max-age-0.js", ja=["js_css_ohne_cache"])
    _mit_skript(w, "/js-expires", "/js/expires.js", nein=["js_css_ohne_cache"])
    _mit_skript(w, "/js-max-age", "/js/max-age.js", nein=["js_css_ohne_cache"])

    w.datei("/js/lesbar.js", _lesbar(3000), JS)
    w.datei("/js/lesbar-klein.js", _lesbar(2000), JS)
    w.datei("/js/minifiziert.js", _einzeilig(3000), JS)
    _mit_skript(w, "/js-lesbar", "/js/lesbar.js", ja=["js_css_nicht_minifiziert"])
    _mit_skript(w, "/js-lesbar-klein", "/js/lesbar-klein.js", nein=["js_css_nicht_minifiziert"],
                warum={"js_css_nicht_minifiziert": "unter 2 KB wird nicht bewertet"})
    _mit_skript(w, "/js-minifiziert", "/js/minifiziert.js", nein=["js_css_nicht_minifiziert"])

    w.datei("/js/klein.js", "var k=1;", JS)
    w.seite("/skript-im-head", kopf='<script src="/js/klein.js"></script>', ja=["skripte_blockierend"])
    w.seite("/skript-defer", kopf='<script src="/js/klein.js" defer></script>', nein=["skripte_blockierend"])
    w.seite("/skript-async", kopf='<script src="/js/klein.js" async></script>', nein=["skripte_blockierend"])
    w.seite("/skript-module", kopf='<script src="/js/klein.js" type="module"></script>', nein=["skripte_blockierend"])
    w.seite("/css-im-head", kopf='<link rel="stylesheet" href="/css/datei-001.css">', nein=["skripte_blockierend"],
            warum={"skripte_blockierend": "Prüfung gilt nur Skripten; Stylesheets im head sind normal (DataForSEO meldet sie)"})
    _mit_skript(w, "/skript-am-ende", "/js/klein.js", nein=["skripte_blockierend"])
