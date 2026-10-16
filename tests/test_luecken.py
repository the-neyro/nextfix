"""Phase 5: Themen-Lücke zu einem Mitbewerber (auf vorbereiteten Crawl-Zeilen)."""

import pytest
from fastapi.testclient import TestClient

from app.core import luecken, projekte
from app.db import verbinden


def crawl(conn, projekt_id: int, seiten: list[tuple[str, str]]) -> None:
    """Fertigen Crawl mit Seiten (Title, H1) anlegen."""
    c = conn.execute("INSERT INTO crawls (projekt_id, start_url, status) VALUES (?, 'https://x/', 'fertig')",
                     (projekt_id,)).lastrowid
    for i, (title, h1) in enumerate(seiten):
        conn.execute("INSERT INTO seiten (crawl_id, url, tiefe, status_code, title, h1_text) VALUES (?, ?, 1, 200, ?, ?)",
                     (c, f"https://x/{projekt_id}/{i}", title, h1))
    conn.commit()


VORLAGE = "Wir freuen uns auf Ihre Anfrage"


@pytest.fixture
def conn():
    c = verbinden()
    projekte.anlegen(c, "ich.de")
    projekte.anlegen(c, "konkurrent.de")
    crawl(c, 1, [("SEO Check kostenlos | Ich", "SEO Check"), ("Webdesign Tipps | Ich", "Webdesign")])
    crawl(c, 2, [("Webdesign Hamburg | Konkurrent", VORLAGE), ("App-Entwicklung für iOS | Konkurrent", VORLAGE),
                 ("App-Entwicklung für Android | Konkurrent", VORLAGE), ("Webdesign für KMU | Konkurrent", VORLAGE),
                 ("Online Marketing Hamburg | Konkurrent", VORLAGE), ("Konkurrent Kontakt", VORLAGE)])
    return c


def test_wortgruppen():
    g = luecken.wortgruppen("App-Entwicklung für iOS | Konkurrent", {"konkurrent"})
    assert {"app-entwicklung", "ios", "app-entwicklung für ios"} <= g
    assert "für" not in g and "für ios" not in g and not any("konkurrent" in x for x in g)


def test_luecke(conn):
    l = luecken.luecke(conn, 1, 2)
    themen = {t["begriff"]: t for t in l["luecken"]}
    assert themen["hamburg"]["seiten_mitbewerber"] == 2 and themen["app-entwicklung"]["seiten_mitbewerber"] == 2
    assert "webdesign" not in themen  # habe ich selbst
    assert not any("freuen" in b or "anfrage" in b for b in themen)  # Vorlagen-H1 zählt nur einmal
    assert "ios" not in themen and "kmu" not in themen  # nur einmal beim Mitbewerber
    assert l["gemeinsam"] >= 1 and (l["seiten_eigen"], l["seiten_mitbewerber"]) == (2, 6)


def test_fehler(conn):
    projekte.anlegen(conn, "leer.de")
    with pytest.raises(luecken.LueckenFehler, match="kein fertiger Crawl"):
        luecken.luecke(conn, 1, 3)
    with pytest.raises(luecken.LueckenFehler, match="anderes Projekt"):
        luecken.luecke(conn, 1, 1)


def test_ui_und_api(conn):
    from app.web import app
    client = TestClient(app)
    assert "konkurrent.de" in client.get("/projekte/1/keywords").text
    seite = client.get("/projekte/1/keywords/luecke?mitbewerber_id=2").text
    assert "Themen-Lücke: konkurrent.de" in seite and "hamburg" in seite
    assert client.get("/api/projekte/1/keywords/luecke?mitbewerber_id=2").json()["luecken_gesamt"] >= 2
    assert client.get("/api/projekte/1/keywords/luecke?mitbewerber_id=1").status_code == 400
