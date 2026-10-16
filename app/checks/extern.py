"""Checks: defekte externe Ziele (Links, Bilder, JS, CSS)."""

from app.checks.katalog import abfrage, check
from app.checks.technik import _RESSOURCE_DEFEKT


@check("externe_links_defekt", "Defekte externe Links", "warning", "links",
       "Links auf nicht mehr vorhandene fremde Seiten frustrieren Besucher und wirken ungepflegt.",
       "Link auf eine funktionierende Adresse ändern oder entfernen.")
def externe_links_defekt(conn, crawl_id):
    return abfrage(conn, _RESSOURCE_DEFEKT.format(arten="'a'", extern=1), crawl_id)


@check("externe_bilder_defekt", "Defekte externe Bilder", "warning", "technik",
       "Von fremden Servern eingebundene Bilder fehlen, wenn der Server sie entfernt hat oder blockiert.",
       "Bild selbst hosten oder eine funktionierende Quelle einbinden.")
def externe_bilder_defekt(conn, crawl_id):
    return abfrage(conn, _RESSOURCE_DEFEKT.format(arten="'img'", extern=1), crawl_id)


@check("externe_js_css_defekt", "Defekte externe JS- und CSS-Dateien", "warning", "technik",
       "Fällt ein eingebundenes fremdes Skript oder Stylesheet aus, kann die Seite falsch aussehen oder nicht funktionieren.",
       "Adresse prüfen, auf eine aktuelle Version umstellen oder die Datei selbst hosten.")
def externe_js_css_defekt(conn, crawl_id):
    return abfrage(conn, _RESSOURCE_DEFEKT.format(arten="'script', 'css'", extern=1), crawl_id)
