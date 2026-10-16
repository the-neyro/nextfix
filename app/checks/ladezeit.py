"""Ladezeit (Core Web Vitals, Labor): Treffer aus dem letzten fertigen Messlauf des Crawls, nur mobil.

Mobil, weil Google die mobile Fassung bewertet. Gemessen wird nur eine Stichprobe (Startseite + stärkste Seiten),
deshalb zählt der Anteil betroffener Seiten gegen die gemessenen Seiten, nicht gegen alle (siehe app/core/audit.py).
Ohne Messung gibt es keine Treffer; nach jeder Messung wird der Crawl neu ausgewertet (app/core/vitals.py).
"""

from app.checks.katalog import check
from app.crawler.vitals import SCHWELLEN

STICHPROBE = {"ladezeit_lcp", "ladezeit_cls", "ladezeit_tbt"}

_LETZTER_LAUF = "(SELECT MAX(id) FROM vitals_laeufe WHERE crawl_id = ? AND status = 'fertig')"


def gemessen(conn, crawl_id) -> int:
    """Anzahl erfolgreich gemessener Seiten (mobil) im letzten fertigen Messlauf."""
    return conn.execute(f"SELECT COUNT(*) FROM vitals WHERE lauf_id = {_LETZTER_LAUF} AND geraet = 'mobile'"
                        " AND fehler IS NULL", (crawl_id,)).fetchone()[0]


def _schlecht(conn, crawl_id, metrik: str, text) -> list:
    zeilen = conn.execute(f"""
        SELECT s.id, v.{metrik} FROM vitals v JOIN seiten s ON s.crawl_id = ? AND s.url = v.url
        WHERE v.lauf_id = {_LETZTER_LAUF} AND v.geraet = 'mobile' AND v.fehler IS NULL AND v.{metrik} > ?""",
                          (crawl_id, crawl_id, SCHWELLEN[metrik][1]))
    return [(z[0], text(z[1])) for z in zeilen]


@check("ladezeit_lcp", "Hauptinhalt lädt langsam (LCP mobil über 4 s)", "warning", "performance",
       "Der größte sichtbare Inhalt erscheint auf dem Handy erst nach über 4 Sekunden. LCP gehört zu den Core Web "
       "Vitals, die Google fürs Ranking nutzt, und viele Besucher springen vorher ab.",
       "Hauptbild verkleinern (WebP/AVIF, passende Größe) und nicht lazy laden, sondern vorladen; Server-Antwort "
       "beschleunigen und render-blockierende Skripte und Styles reduzieren.")
def ladezeit_lcp(conn, crawl_id):
    return _schlecht(conn, crawl_id, "lcp", lambda w: f"LCP {w / 1000:.1f} s (mobil)".replace(".", ","))


@check("ladezeit_cls", "Layout springt beim Laden (CLS mobil über 0,25)", "warning", "performance",
       "Inhalte verschieben sich während des Ladens, Besucher klicken daneben. CLS gehört zu den Core Web Vitals.",
       "Bildern, Videos und Einbettungen feste Breite und Höhe geben, Platz für Banner reservieren, Schriften mit "
       "font-display und passender Ersatzschrift laden.")
def ladezeit_cls(conn, crawl_id):
    return _schlecht(conn, crawl_id, "cls", lambda w: f"CLS {w:.2f} (mobil)".replace(".", ","))


@check("ladezeit_tbt", "Seite reagiert träge (TBT mobil über 600 ms)", "warning", "performance",
       "Lange JavaScript-Aufgaben blockieren die Seite, Klicks reagieren verzögert. TBT ist im Labor der Ersatz "
       "für INP, das dritte Core Web Vital.",
       "Unnötige Skripte entfernen oder mit defer laden, Drittanbieter-Tags (Tracking, Chat, Werbung) prüfen, "
       "große JavaScript-Pakete aufteilen.")
def ladezeit_tbt(conn, crawl_id):
    return _schlecht(conn, crawl_id, "tbt", lambda w: f"TBT {w} ms (mobil)")
