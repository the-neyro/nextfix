"""Klartext-Anleitungen: die häufigsten Aufgaben sind ohne Fachwörter erklärt und sagen, wo es in WordPress geht."""

import re

from fastapi.testclient import TestClient

from app.checks import REGISTER
from app.web import app

client = TestClient(app)

HAEUFIGSTE = ["wenig_text", "meta_desc_doppelt", "meta_desc_fehlt", "meta_desc_zu_kurz", "title_zu_lang",
              "title_fehlt", "bilder_ohne_alt", "status_4xx", "interne_links_defekt", "sitemap_falsche_seiten"]
# Fachwörter, die ein Laie nicht kennt; „noindex“ und „301“ nur in Anführungszeichen als erklärter Begriff
VERBOTEN = ["Crawl-Budget", "Status 200", "4xx", "indexierbar", "URL", "alt=", "Title-Tag", "Meta-Description"]


def test_haeufigste_aufgaben_in_klartext_mit_wordpress():
    for cid in HAEUFIGSTE:
        c = REGISTER[cid]
        text = c.warum + " " + c.beheben
        assert c.wordpress and ("Yoast" in c.wordpress or "Rank Math" in c.wordpress or "Editor" in c.wordpress), cid
        for wort in VERBOTEN:
            assert wort not in text, (cid, wort)
        for begriff in ("noindex", "301"):
            for treffer in re.finditer(begriff, text):
                assert text[treffer.start() - 1] == "„", (cid, begriff)   # nur als erklärter Begriff „noindex“


def test_wordpress_hinweis_in_oberflaeche_und_aufgaben(testseite):
    pid = client.post("/api/projekte", json={"domain": "127.0.0.1"}).json()["id"]
    client.put(f"/api/projekte/{pid}/einstellungen", json={"start_url": testseite, "crawl_delay": 0})
    cid = client.post(f"/api/projekte/{pid}/crawls?warten=true").json()["id"]
    assert "In WordPress:" in client.get(f"/crawls/{cid}/issues/status_4xx/seite").text
    aufgabe = next(a for a in client.get(f"/api/crawls/{cid}/aufgaben").json()["aufgaben"] if a["id"] == "status_4xx")
    assert "Redirection" in aufgabe["wordpress"]
