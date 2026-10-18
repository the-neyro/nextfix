"""Paket C (Produktreife): Ladezeit-Stichprobe ohne noindex, ETag zählt wie Last-Modified."""
from app.checks.technik import ohne_last_modified
from app.core import vitals
from app.db import verbinden


def _crawl(conn) -> int:
    conn.execute("INSERT INTO projekte (id, name, domain) VALUES (1, 'x', 'x.de')")
    conn.execute("INSERT INTO crawls (id, projekt_id, start_url, status) VALUES (1, 1, 'https://x.de/', 'fertig')")
    return 1


def _seite(conn, url, **spalten):
    werte = {"crawl_id": 1, "url": url, "tiefe": 0, "status_code": 200, "content_type": "text/html", "woerter": 300, "blockiert": 0}
    werte.update(spalten)
    conn.execute(f"INSERT INTO seiten ({', '.join(werte)}) VALUES ({', '.join('?' * len(werte))})", tuple(werte.values()))


def test_ladezeit_stichprobe_ohne_noindex(tmp_path):
    conn = verbinden(tmp_path / "t.db")
    _crawl(conn)
    _seite(conn, "https://x.de/")
    _seite(conn, "https://x.de/demo/", meta_robots="noindex")
    _seite(conn, "https://x.de/kopf/", x_robots_tag="noindex, nofollow")
    _seite(conn, "https://x.de/blog/")
    assert vitals.seiten_auswahl(conn, 1, 10) == ["https://x.de/", "https://x.de/blog/"]


def test_etag_reicht_statt_last_modified(tmp_path):
    conn = verbinden(tmp_path / "t.db")
    _crawl(conn)
    _seite(conn, "https://x.de/", etag='"abc"')
    _seite(conn, "https://x.de/b/", last_modified="Sat, 18 Oct 2026 10:00:00 GMT")
    assert ohne_last_modified(conn, 1) == []
    _seite(conn, "https://x.de/c/")
    assert ohne_last_modified(conn, 1) != []


def test_csv_ohne_formeln():
    """Fremder Text wie ein Titel „=1+1“ darf in Excel nicht als Formel laufen; Zahlen bleiben Zahlen."""
    from app.core.export import _csv
    text = _csv(["a", "b", "c"], [("=1+1", -3, "@SUMME(A1)"), ("normal", 5, "-minus")])
    assert "'=1+1;-3;'@SUMME(A1)" in text and "normal;5;'-minus" in text
