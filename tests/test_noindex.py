"""noindex-Seiten erscheinen nicht bei Google: Titel, Beschreibung, Überschriften und doppelter Inhalt zählen dort nicht."""

from tests.test_paket_c import db, seite, treffer  # noqa: F401  (db ist eine Fixture)

SIG = list(range(64))   # gleiche Signatur = gleicher Haupttext


def test_snippet_checks_ignorieren_noindex(db):
    conn, c = db
    for pfad in ("demo/a", "demo/b"):
        seite(conn, c, pfad, title="Demo", meta_robots="noindex, follow", h1_anzahl=0, signatur=SIG)
    seite(conn, c, "demo/c", title="", x_robots_tag="NOINDEX")
    seite(conn, c, "eins", title="Gleich", meta_description="Text", h1_anzahl=1)
    seite(conn, c, "zwei", title="Gleich", h1_anzahl=1)

    assert treffer(conn, c, "title_doppelt") == {"eins": "Gleich", "zwei": "Gleich"}
    assert treffer(conn, c, "meta_desc_fehlt") == {"zwei": None}
    assert treffer(conn, c, "title_fehlt") == {}
    assert treffer(conn, c, "h1_fehlt") == {}
    assert treffer(conn, c, "duplicate_content") == {}


def test_doppelter_inhalt_zaehlt_ohne_noindex_weiter(db):
    conn, c = db
    seite(conn, c, "a", signatur=SIG)
    seite(conn, c, "b", signatur=SIG)
    assert set(treffer(conn, c, "duplicate_content")) == {"a", "b"}
