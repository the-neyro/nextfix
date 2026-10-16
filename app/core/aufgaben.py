"""„Was jetzt tun“: Probleme eines Crawls als priorisierte Aufgaben (siehe docs/ui/ux-ablaeufe.md, Abschnitt 3).

Reihenfolge = Punkte, die der Website-Zustand (Health) gewinnt, wenn nur dieses Problem behoben ist – mit der Formel
aus app/core/score.py, damit Liste und Zustandszahl zusammenpassen. Bei gleichem Gewinn zuerst der geringere Aufwand.
Feinschliff (Notices, Gewicht 0) kommt nicht in die Liste, sondern getrennt darunter.

Angezeigt wird nur die Wirkung als Stufe (hoch / mittel / gering), keine Punktzahl: Die Punkte stammen aus unserer
eigenen Formel und sagen nichts darüber, was eine Behebung bei Rankings oder Besuchern bringt. Eine Zahl wie „+4,2“
täuscht eine Genauigkeit vor, die es nicht gibt. „gewinn“ bleibt für Sortierung und MCP im Ergebnis.
"""

import sqlite3

from app import checks
from app.core import score

STUFEN = {"error": "dringend", "warning": "wichtig", "notice": "feinschliff"}

# Aufwand: 1 = einmal einstellen (Server, Template, Datei), 2 = kurz je Seite, 3 = Text schreiben
AUFWAND_TEXT = {1: "einmal einstellen", 2: "kurz je Seite", 3: "Text schreiben"}
AUFWAND_BEREICH = {"crawlbarkeit": 1, "https": 1, "technik": 1, "performance": 1, "international": 1,
                   "links": 2, "inhalt": 2, "ki": 3}
AUFWAND_CHECK = {"status_4xx": 2, "wenig_text": 3, "duplicate_content": 3, "ki_bots_blockiert": 1,
                 "llms_fehlt": 1, "llms_format": 1, "llms_duenn": 1, "llms_tote_links": 1, "ki_ohne_entitaet": 1,
                 "ki_artikel_ohne_autor_datum": 1, "ki_ohne_hauptbereich": 1, "viewport_fehlt": 1,
                 "langsame_seite": 1, "text_html_niedrig": 3}
# Wer macht es: selbst im CMS oder Technik (Hoster, Entwickler)
TECHNIK_BEREICHE = {"crawlbarkeit", "https", "technik", "performance", "international"}
SELBST_CHECKS = {"status_4xx", "canonical_defekt", "markup_fehlerhaft", "redirect_kette", "temp_redirect"}
TECHNIK_CHECKS = {"ki_bots_blockiert", "llms_fehlt", "llms_format", "ki_ohne_hauptbereich", "zu_viele_parameter"}

# Aufgabe als Handlung; {n} = Anzahl betroffener Seiten. Fehlt ein Eintrag, gilt der Check-Name.
HANDLUNG = {
    "interne_links_defekt": "Repariere defekte interne Links auf {n}",
    "externe_links_defekt": "Repariere Links auf fremde Seiten, die nicht mehr gehen ({n})",
    "status_4xx": "Behebe {n} mit „nicht gefunden“ (404)",
    "status_5xx": "Lass {n} mit Serverfehler prüfen",
    "nicht_erreichbar": "Kläre, warum {n} nicht laden",
    "redirect_kette": "Kürze Weiterleitungsketten auf {n}",
    "temp_redirect": "Mach vorübergehende Weiterleitungen dauerhaft ({n})",
    "title_fehlt": "Gib {n} einen Seitentitel",
    "title_doppelt": "Gib {n} eigene Seitentitel",
    "title_zu_lang": "Kürze den Seitentitel von {n} auf 70 Zeichen",
    "title_zu_kurz": "Verlängere zu kurze Seitentitel ({n})",
    "meta_desc_fehlt": "Schreib eine Beschreibung für {n}",
    "meta_desc_doppelt": "Gib {n} eigene Beschreibungen",
    "h1_fehlt": "Gib {n} eine Hauptüberschrift (H1)",
    "h1_gleich_title": "Formuliere H1 und Seitentitel unterschiedlich ({n})",
    "wenig_text": "Bau {n} mit wenig Text aus oder nimm sie aus dem Index",
    "duplicate_content": "Führe {n} mit fast gleichem Inhalt zusammen",
    "bilder_ohne_alt": "Ergänze Bildbeschreibungen (alt) auf {n}",
    "text_html_niedrig": "Mehr Text, weniger Code auf {n}",
    "canonical_defekt": "Korrigiere die Hauptversion (Canonical) auf {n}",
    "mehrere_canonicals": "Lass nur eine Hauptversion (Canonical) je Seite stehen ({n})",
    "markup_fehlerhaft": "Korrigiere fehlerhafte strukturierte Daten auf {n}",
    "viewport_fehlt": "Mach {n} handytauglich (Viewport-Tag)",
    "langsame_seite": "Mach {n} schneller (Server antwortet über 1 s)",
    "ladezeit_lcp": "Lass den Hauptinhalt auf {n} schneller laden (Handy)",
    "ladezeit_cls": "Verhindere, dass das Layout auf {n} beim Laden springt",
    "ladezeit_tbt": "Mach {n} reaktionsschneller (weniger JavaScript)",
    "mixed_content": "Lade Bilder und Skripte auf {n} über https://",
    "https_verlinkt_http": "Stell Links auf {n} von http:// auf https:// um",
    "sitemap_fehlt": "Leg eine sitemap.xml an",
    "sitemap_nicht_in_robots": "Trag die Sitemap in die robots.txt ein",
    "sitemap_falsche_seiten": "Entferne fehlerhafte Adressen aus der Sitemap",
    "robots_formatfehler": "Korrigiere Tippfehler in der robots.txt",
    "inhalt_nur_per_js": "Liefere den Inhalt von {n} schon im HTML aus, nicht erst per JavaScript",
    "ki_bots_blockiert": "Lass KI-Suchdienste in der robots.txt zu",
    "llms_tote_links": "Korrigiere tote Links in der llms.txt",
    "js_css_unkomprimiert": "Lass Skripte und Styles komprimiert ausliefern ({n})",
    "js_css_ohne_cache": "Lass Skripte und Styles im Browser zwischenspeichern ({n})",
    "unkomprimiert": "Lass Seiten komprimiert ausliefern ({n})",
    "interne_links_nofollow": "Entferne nofollow von internen Links ({n})",
    "unterstriche_url": "Nutze Bindestriche statt Unterstriche in Adressen ({n})",
    "ohne_lang": "Gib die Sprache der Seite an (lang) – {n}",
    "zertifikat_ablauf": "Erneuere das SSL-Zertifikat",
    "http_nicht_auf_https": "Leite http:// dauerhaft auf https:// um",
    "www_aufloesung": "Leite die www- bzw. Nicht-www-Adresse dauerhaft um",
}


# Wirkung nach Abzug des Problems (Gewicht × Anteil betroffener Seiten, siehe score.strafe), unabhängig vom
# Gesamtzustand: Fehler zählen mindestens „mittel“, ab etwa einem Fünftel der Seiten „hoch“; Warnungen werden erst
# auf vielen Seiten (ab etwa 30 %) „mittel“ und site-weit „hoch“.
WIRKUNG_HOCH = 1.0
WIRKUNG_MITTEL = 0.4


def wirkung(abzug: float) -> str:
    return "hoch" if abzug >= WIRKUNG_HOCH else "mittel" if abzug >= WIRKUNG_MITTEL else "gering"


def _seiten_text(n: int, ganze_site: bool) -> str:
    if ganze_site:
        return "die ganze Website"
    return "1 Seite" if n == 1 else f"{n} Seiten"


def _aufwand(c) -> int:
    return AUFWAND_CHECK.get(c.id, AUFWAND_BEREICH.get(c.kategorie, 2))


def _wer(c) -> str:
    if c.id in SELBST_CHECKS:
        return "selbst"
    if c.id in TECHNIK_CHECKS or c.kategorie in TECHNIK_BEREICHE:
        return "Technik"
    return "selbst"


def handlung(c, seiten: int, ganze_site: bool) -> str:
    vorlage = HANDLUNG.get(c.id)
    return vorlage.format(n=_seiten_text(seiten, ganze_site)) if vorlage else c.name


def _vorheriger_crawl(conn: sqlite3.Connection, crawl_id: int) -> int | None:
    z = conn.execute("""SELECT v.id FROM crawls v JOIN crawls c ON c.projekt_id = v.projekt_id
                        WHERE c.id = ? AND v.id < c.id AND v.status IN ('fertig', 'abgebrochen')
                        ORDER BY v.id DESC LIMIT 1""", (crawl_id,)).fetchone()
    return z[0] if z else None


def liste(conn: sqlite3.Connection, crawl_id: int) -> dict:
    """{"aufgaben": [...], "feinschliff": [...], "erledigt": [...], "vorher_id": int | None}."""
    from app.core import audit   # zirkulären Import vermeiden

    treffer = audit._treffer_pro_check(conn, crawl_id)
    aus = audit._ausgeschlossen(conn, crawl_id)
    geprueft = audit._geprueft(conn, crawl_id)
    aktiv = [c for c in checks.REGISTER.values() if c.id not in aus]
    bezug = audit._bezug(conn, crawl_id)
    abzug = {c.id: score.strafe(c.schwere, treffer[c.id][1], treffer[c.id][2], bezug.get(c.id, geprueft), c.id)
             for c in aktiv if c.id in treffer}
    gesamt = sum(abzug.values())

    vorher_id = _vorheriger_crawl(conn, crawl_id)
    vorher = audit._treffer_pro_check(conn, vorher_id) if vorher_id else {}

    aufgaben, feinschliff = [], []
    for c in aktiv:
        if c.id not in treffer:
            continue
        _, seiten, ganze_site = treffer[c.id]
        gewinn = score.aus_abzug(gesamt - abzug[c.id]) - score.aus_abzug(gesamt)
        if vorher_id is None:
            verlauf = None
        elif c.id not in vorher:
            verlauf = "neu"
        else:
            alt = vorher[c.id][1]
            verlauf = "besser" if seiten < alt else "schlimmer" if seiten > alt else "gleich"
        a = {"id": c.id, "name": c.name, "was": handlung(c, seiten, ganze_site), "warum": c.warum,
             "beheben": c.beheben, "schwere": c.schwere, "stufe": STUFEN[c.schwere], "kategorie": c.kategorie,
             "seiten": seiten, "ganze_site": ganze_site, "seiten_text": _seiten_text(seiten, ganze_site),
             "gewinn": round(gewinn, 1), "wirkung": wirkung(abzug[c.id]), "aufwand": _aufwand(c), "aufwand_text": AUFWAND_TEXT[_aufwand(c)],
             "wer": _wer(c), "verlauf": verlauf, "vorher": vorher.get(c.id, (0, 0, False))[1]}
        (feinschliff if c.schwere == "notice" else aufgaben).append(a)

    aufgaben.sort(key=lambda a: (-a["gewinn"], a["aufwand"], -a["seiten"]))
    feinschliff.sort(key=lambda a: -a["seiten"])
    erledigt = [{"id": cid, "name": checks.REGISTER[cid].name, "seiten": v[1]}
                for cid, v in vorher.items()
                if cid in checks.REGISTER and cid not in treffer and cid not in aus
                and checks.REGISTER[cid].schwere != "notice"]
    return {"aufgaben": aufgaben, "feinschliff": feinschliff, "erledigt": erledigt, "vorher_id": vorher_id}
