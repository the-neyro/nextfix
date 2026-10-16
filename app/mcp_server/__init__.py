"""MCP-Server: gibt Claude Zugriff auf alle Kern-Funktionen.

Start (stdio): .venv/bin/python -m app.mcp_server
Regel: jede neue Kern-Funktion bekommt hier ein Tool.
"""

import asyncio
from contextlib import closing

from mcp.server import MCPServer

from app import berichte, config
from app.core import audit, ausblenden, export, gsc_konto, importe, keywords, luecken, onpage, positionen, vitals, projekte, themen, tracking, vergleich
from app.db import verbinden

server = MCPServer(
    name="seo-tool",
    instructions=(
        "Lokales SEO-Tool (Site Audit). Tools arbeiten auf derselben Datenbank wie die Web-UI "
        "(http://localhost:8000). Ablauf: projekt_anlegen → einstellungen_setzen (optional) → "
        "crawl_starten → uebersicht / issues_liste / issue_details / seiten_liste. "
        "Nach mehreren Crawls: verlauf, crawl_vergleich, treffer_vergleich. "
        "Absichtlich so (z. B. Login-Seite ohne Text)? ausblenden → zählt nicht mehr im Zustand; einblenden nimmt es zurück. "
        "Position Tracking: gsc_status / gsc_test (Zugang prüfen) → positionen_import (quelle gsc oder mock) → "
        "positionen_uebersicht / "
        "positionen_keywords / keyword_verlauf. Tracking-Liste (tracking_*): ist sie gefüllt, zählen nur "
        "ihre Begriffe in Sichtbarkeit und Kennzahlen. Keyword-Recherche: keyword_recherche_starten → "
        "keyword_recherchen (Status) → keyword_ideen."
    ),
)


def _db():
    return closing(verbinden())


# ---------- Projekte ----------

@server.tool()
def projekte_liste() -> list[dict]:
    """Alle Projekte (Websites) mit ID, Name, Domain."""
    with _db() as conn:
        return [p.als_dict() for p in projekte.liste(conn)]


@server.tool()
def projekt_anlegen(domain: str, name: str | None = None) -> dict:
    """Neues Projekt für eine Domain anlegen. Domain darf mit oder ohne https:// kommen."""
    with _db() as conn:
        return projekte.anlegen(conn, domain, name).als_dict()


@server.tool()
def projekt_loeschen(projekt_id: int) -> str:
    """Projekt mit allen Crawls und Daten löschen."""
    with _db() as conn:
        projekte.loeschen(conn, projekt_id)
    return f"Projekt {projekt_id} gelöscht"


# ---------- Einstellungen ----------

@server.tool()
def einstellungen_holen(projekt_id: int) -> dict:
    """Crawl-Einstellungen eines Projekts: start_url, seitenlimit, crawl_delay, user_agent, robots_beachten, quelle,
    erlauben, sperren, parameter_entfernen, checks_aus (Listen: ein Eintrag pro Zeile)."""
    with _db() as conn:
        return audit.einstellungen_holen(conn, projekt_id)


@server.tool()
def einstellungen_setzen(projekt_id: int, start_url: str | None = None, seitenlimit: int | None = None,
                         crawl_delay: float | None = None, user_agent: str | None = None,
                         robots_beachten: bool | None = None, quelle: str | None = None,
                         erlauben: list[str] | None = None, sperren: list[str] | None = None,
                         parameter_entfernen: list[str] | None = None, checks_aus: list[str] | None = None) -> dict:
    """Crawl-Einstellungen ändern. Nur übergebene Werte werden geändert; eine leere Liste leert das Feld.
    quelle: 'website' (Links ab Start-URL folgen), 'sitemap' (nur URLs aus den Sitemaps) oder 'beides'
    (Links folgen, danach verwaiste Sitemap-URLs mit prüfen).
    erlauben/sperren: Pfad-Masken wie in robots.txt, z. B. "/blog/", "/shop/*/details", "sort=".
    parameter_entfernen: URL-Parameter, die ignoriert werden, z. B. "utm_source" oder "*" für alle.
    checks_aus: Check-IDs (siehe checks_katalog), die nicht ausgewertet werden und nicht in den Health Score zählen."""
    with _db() as conn:
        return audit.einstellungen_setzen(
            conn, projekt_id, start_url=start_url, seitenlimit=seitenlimit, crawl_delay=crawl_delay,
            user_agent=user_agent, robots_beachten=robots_beachten, quelle=quelle, erlauben=erlauben,
            sperren=sperren, parameter_entfernen=parameter_entfernen, checks_aus=checks_aus)


# ---------- Crawls ----------

@server.tool()
async def crawl_starten(projekt_id: int, warten: bool = True) -> dict:
    """Site Audit starten. warten=True blockiert bis zum Ende (für kleine Sites),
    warten=False startet im Hintergrund; Status dann mit crawl_status abfragen."""
    def starten():
        with _db() as conn:
            return audit.crawl_starten(conn, projekt_id, warten=warten)
    return await asyncio.to_thread(starten)


@server.tool()
def crawl_status(crawl_id: int) -> dict:
    """Status eines Crawls: laeuft | fertig | abgebrochen | fehler, Seitenanzahl, Health."""
    with _db() as conn:
        return audit.crawl_holen(conn, crawl_id)


@server.tool()
def crawls_liste(projekt_id: int) -> list[dict]:
    """Alle Crawls eines Projekts, neueste zuerst."""
    with _db() as conn:
        return audit.crawls_liste(conn, projekt_id)


@server.tool()
def crawl_abbrechen(crawl_id: int) -> dict:
    """Laufenden Crawl stoppen. Bisherige Ergebnisse bleiben erhalten und werden ausgewertet."""
    with _db() as conn:
        return audit.crawl_abbrechen(conn, crawl_id)


# ---------- Auswertung ----------

def _crawl_id(conn, crawl_id: int | None, projekt_id: int | None) -> int:
    if crawl_id:
        return crawl_id
    if projekt_id:
        letzte = audit.letzter_crawl_id(conn, projekt_id)
        if letzte:
            return letzte
        raise audit.AuditFehler(f"Projekt {projekt_id} hat noch keinen fertigen Crawl")
    raise audit.AuditFehler("crawl_id oder projekt_id angeben")


@server.tool()
def uebersicht(crawl_id: int | None = None, projekt_id: int | None = None) -> dict:
    """Overview eines Crawls: Health Score, Scores je Kategorie, Errors/Warnings/Notices,
    Seiten-Aufteilung, Top-Issues. Ohne crawl_id: letzter fertiger Crawl des Projekts."""
    with _db() as conn:
        return audit.uebersicht(conn, _crawl_id(conn, crawl_id, projekt_id))


@server.tool()
def issues_liste(crawl_id: int | None = None, projekt_id: int | None = None,
                 schwere: str | None = None, kategorie: str | None = None) -> list[dict]:
    """Gefundene Probleme je Check. Filter: schwere (error|warning|notice),
    kategorie (crawlbarkeit|https|links|inhalt|performance|technik|international|ki)."""
    with _db() as conn:
        return audit.issues_liste(conn, _crawl_id(conn, crawl_id, projekt_id), schwere, kategorie)


@server.tool()
def issue_details(check_id: str, crawl_id: int | None = None, projekt_id: int | None = None,
                  limit: int = 100) -> dict:
    """Betroffene URLs eines Checks mit Detail, plus Erklärung und Lösungsvorschlag."""
    with _db() as conn:
        return audit.issue_details(conn, _crawl_id(conn, crawl_id, projekt_id), check_id, limit)


@server.tool()
def ausblenden_setzen(projekt_id: int, check_id: str | None = None, url: str | None = None, grund: str = "") -> dict:
    """„Bewusst so“: Problem (check_id), ganze Seite (url) oder ein Problem auf einer Seite (beides) ausblenden.
    Zählt danach nicht mehr in Website-Zustand, Teilnoten und Aufgabenliste – für alle Crawls des Projekts."""
    with _db() as conn:
        return ausblenden.ausblenden(conn, projekt_id, check_id, url, grund)


@server.tool()
def ausblenden_liste(projekt_id: int) -> list[dict]:
    """Alle Ausblendungen („Bewusst so“) eines Projekts mit ID, Problem, Seite und Grund."""
    with _db() as conn:
        return ausblenden.liste(conn, projekt_id)


@server.tool()
def einblenden(projekt_id: int, ausblendung_id: int) -> dict:
    """Ausblendung zurücknehmen (ID aus ausblenden_liste). Problem zählt wieder mit."""
    with _db() as conn:
        ausblenden.einblenden(conn, projekt_id, ausblendung_id)
        return {"ok": True, "ausblendungen": ausblenden.liste(conn, projekt_id)}


@server.tool()
def seiten_liste(crawl_id: int | None = None, projekt_id: int | None = None, suche: str | None = None,
                 nur_mit_problemen: bool = False, limit: int = 100, offset: int = 0) -> list[dict]:
    """Gecrawlte Seiten mit Status, Tiefe, Title, Ladezeit, Wortanzahl und Anzahl Issues."""
    with _db() as conn:
        return audit.seiten_liste(conn, _crawl_id(conn, crawl_id, projekt_id), suche,
                                  nur_mit_problemen, limit, offset)


@server.tool()
def seite_details(url: str, crawl_id: int | None = None, projekt_id: int | None = None) -> dict:
    """Alle gemessenen Daten und Issues einer einzelnen Seite."""
    with _db() as conn:
        return audit.seite_details(conn, _crawl_id(conn, crawl_id, projekt_id), url)


@server.tool()
def verlauf(projekt_id: int) -> list[dict]:
    """Alle abgeschlossenen Crawls eines Projekts (älteste zuerst) mit Health und Issues je Schweregrad."""
    with _db() as conn:
        return vergleich.verlauf(conn, projekt_id)


@server.tool()
def crawl_vergleich(crawl_id: int | None = None, projekt_id: int | None = None,
                    vorher_id: int | None = None) -> dict:
    """Was hat sich geändert? Checks mit Status neu/behoben/mehr/weniger gegenüber dem vorherigen
    (oder vorher_id) Crawl. Ohne crawl_id: letzter fertiger Crawl des Projekts."""
    with _db() as conn:
        return vergleich.vergleich(conn, _crawl_id(conn, crawl_id, projekt_id), vorher_id)


@server.tool()
def treffer_vergleich(check_id: str, crawl_id: int | None = None, projekt_id: int | None = None,
                      vorher_id: int | None = None) -> dict:
    """Für einen Check: URLs, die neu betroffen sind, und URLs, bei denen das Problem behoben ist."""
    with _db() as conn:
        return vergleich.treffer_vergleich(conn, _crawl_id(conn, crawl_id, projekt_id), check_id, vorher_id)


@server.tool()
def thema_bericht(kategorie: str, crawl_id: int | None = None, projekt_id: int | None = None) -> dict:
    """Thematischer Bericht wie in Semrush: Health der Kategorie, ihre Issues und Kennzahlen
    (z. B. Klicktiefe, Link-Stärke, Antwortzeiten, schema.org-Typen).
    kategorie: crawlbarkeit|https|links|inhalt|performance|technik|international|ki."""
    with _db() as conn:
        return themen.thema(conn, _crawl_id(conn, crawl_id, projekt_id), kategorie)


@server.tool()
async def pdf_bericht(crawl_id: int | None = None, projekt_id: int | None = None) -> str:
    """Site-Audit-Bericht als PDF (Deckblatt, Zusammenfassung, wichtigste Probleme, alle Themen) speichern;
    gibt den Dateipfad zurück."""
    def erzeugen() -> str:
        with _db() as conn:
            cid = _crawl_id(conn, crawl_id, projekt_id)
            inhalt = berichte.site_audit_pdf(conn, cid)
        ordner = config.DB_PFAD.parent / "export"
        ordner.mkdir(parents=True, exist_ok=True)
        pfad = ordner / f"site-audit-crawl-{cid}.pdf"
        pfad.write_bytes(inhalt)
        return str(pfad)
    return await asyncio.to_thread(erzeugen)  # Playwright-Sync-API nicht im Event-Loop


@server.tool()
def csv_export(art: str, crawl_id: int | None = None, projekt_id: int | None = None) -> str:
    """CSV-Datei (Semikolon, UTF-8 mit BOM für Excel) speichern; gibt den Dateipfad zurück.
    art: issues (ein Treffer pro Zeile) | seiten (alle gecrawlten Seiten mit Messwerten)."""
    funktionen = {"issues": export.issues_csv, "seiten": export.seiten_csv}
    if art not in funktionen:
        raise audit.AuditFehler(f"Unbekannter Export: {art} (issues | seiten)")
    with _db() as conn:
        cid = _crawl_id(conn, crawl_id, projekt_id)
        inhalt = funktionen[art](conn, cid)
    ordner = config.DB_PFAD.parent / "export"
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"crawl-{cid}-{art}.csv"
    pfad.write_text(inhalt, encoding="utf-8")
    return str(pfad)


@server.tool()
def checks_katalog() -> list[dict]:
    """Alle verfügbaren Checks mit Schweregrad, Kategorie, Erklärung und Lösung."""
    return audit.checks_katalog()


# ---------- Position Tracking (Search Console) ----------

@server.tool()
def positionen_import(projekt_id: int, quelle: str = "mock", tage: int = 90, warten: bool = False) -> dict:
    """Search-Console-Daten der letzten `tage` Tage ins lokale Archiv holen (max. 480).
    quelle: gsc (Search Console) | bing (Bing Webmaster) – Schlüssel nötig, siehe gsc_status –
    oder mock / bing_mock (Testdaten).
    Läuft im Hintergrund (ca. 1 Anfrage pro Tag); Fortschritt mit import_status. warten=True blockiert."""
    with _db() as conn:
        return importe.starten(conn, projekt_id, quelle, tage, warten=warten)


@server.tool()
def import_status(projekt_id: int, limit: int = 5) -> list[dict]:
    """Letzte Importe eines Projekts: status (laeuft|fertig|fehler), tage_fertig/tage_gesamt, zeilen, fehler_text,
    ausloeser (hand|auto)."""
    with _db() as conn:
        return importe.liste(conn, projekt_id, limit)


@server.tool()
def auto_import_setzen(projekt_id: int, quelle: str | None = None, suchmaschine: str | None = None) -> dict:
    """Täglichen Auto-Import ein- (quelle gsc|mock|bing|bing_mock) oder ausschalten (quelle leer + suchmaschine
    google|bing). Je Suchmaschine eine Quelle. Läuft, solange die Web-App läuft: beim Start und alle 30 Min.
    wird geprüft, ob neue Tage fehlen. Gibt den Stand je Suchmaschine zurück."""
    with _db() as conn:
        return importe.auto_setzen(conn, projekt_id, quelle, suchmaschine)


@server.tool()
def positionen_loeschen(projekt_id: int, quelle: str | None = None) -> str:
    """Gespeicherte Search-Console-Daten löschen (optional nur eine Quelle, z. B. mock)."""
    with _db() as conn:
        return f"{positionen.daten_loeschen(conn, projekt_id, quelle)} Zeilen gelöscht"


@server.tool()
def positionen_uebersicht(projekt_id: int, tage: int = 28, land: str | None = None,
                          geraet: str | None = None, auswahl: str | None = None, tag: str | None = None,
                          suchmaschine: str = "google") -> dict:
    """Position Tracking wie in Semrush: Sichtbarkeit, Ø-Position, Klicks, Verteilung Top 3/10/20/100,
    Gewinner/Verlierer, Striking Distance (Pos. 8–20), Kannibalisierung, Tagesverlauf.
    Vergleich immer mit dem gleich langen Zeitraum davor. land: z. B. deu; geraet: DESKTOP|MOBILE|TABLET.
    auswahl: tracking (nur Tracking-Liste, Standard falls gefüllt) | alle; tag: nur Begriffe mit diesem Tag.
    suchmaschine: google | bing (Bing: Wochenwerte, ohne Seiten/Land/Gerät).
    Listen sind gekürzt (je Begriff nur Kernwerte); Details pro Begriff mit positionen_keywords."""
    with _db() as conn:
        return _kompakt(positionen.uebersicht(conn, projekt_id, tage, land, geraet, auswahl, tag, suchmaschine))


KERNFELDER = ("query", "position", "position_vorher", "aenderung", "klicks", "impressionen", "beste_seite")


def _kompakt(u: dict) -> dict:
    """Spart Tokens: Begriffslisten ohne Seiten-Aufschlüsselung, Striking Distance auf 10 begrenzt."""
    for liste in ("gewinner", "verlierer", "striking"):
        u[liste] = [{f: x[f] for f in KERNFELDER} for x in u[liste][:10]]
    return u


@server.tool()
def positionen_keywords(projekt_id: int, tage: int = 28, land: str | None = None, geraet: str | None = None,
                        suche: str | None = None, sortierung: str = "impressionen", auswahl: str | None = None,
                        tag: str | None = None, suchmaschine: str = "google") -> dict:
    """Alle Suchbegriffe mit Position jetzt/vorher, Änderung (positiv = besser), Klicks, Impressionen, CTR, Seiten.
    sortierung: impressionen|klicks|position|aenderung|query. auswahl/tag wie bei positionen_uebersicht."""
    with _db() as conn:
        return positionen.keywords(conn, projekt_id, tage, land, geraet, suche, sortierung, auswahl, tag,
                                   suchmaschine)


@server.tool()
def keywords_csv(projekt_id: int, tage: int = 28, land: str | None = None, geraet: str | None = None,
                 auswahl: str | None = None, tag: str | None = None, suchmaschine: str = "google") -> str:
    """Suchbegriffe als CSV-Datei speichern (für Excel: Semikolon, UTF-8 mit BOM, Dezimalkomma);
    gibt den Dateipfad zurück. Filter wie positionen_keywords; land z. B. deu, aut, che."""
    with _db() as conn:
        inhalt = export.keywords_csv(conn, projekt_id, tage, land, geraet, auswahl, tag, suchmaschine=suchmaschine)
    ordner = config.DB_PFAD.parent / "export"
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"keywords-{suchmaschine}-projekt-{projekt_id}-{tage}-tage{'-' + land if land else ''}.csv"
    pfad.write_text(inhalt, encoding="utf-8")
    return str(pfad)


@server.tool()
def keyword_verlauf(projekt_id: int, query: str, tage: int = 90, land: str | None = None,
                    geraet: str | None = None, suchmaschine: str = "google") -> dict:
    """Tageswerte (Position, Klicks, Impressionen) eines Suchbegriffs, gesamt und je rankender Seite.
    suchmaschine: google | bing."""
    with _db() as conn:
        return positionen.keyword_verlauf(conn, projekt_id, query, tage, land, geraet, suchmaschine)


# ---------- Tracking-Liste ----------

@server.tool()
def tracking_liste(projekt_id: int, tag: str | None = None) -> dict:
    """Getrackte Suchbegriffe mit Tags (optional nur ein Tag) und alle Tags mit Anzahl."""
    with _db() as conn:
        return {"keywords": tracking.liste(conn, projekt_id, tag), "tags": tracking.alle_tags(conn, projekt_id)}


@server.tool()
def tracking_hinzufuegen(projekt_id: int, queries: list[str], tags: list[str] | None = None) -> dict:
    """Suchbegriffe in die Tracking-Liste aufnehmen (auch solche ohne GSC-Daten) und Tags ergänzen."""
    with _db() as conn:
        return tracking.hinzufuegen(conn, projekt_id, queries, tags)


@server.tool()
def tracking_entfernen(projekt_id: int, queries: list[str]) -> str:
    """Suchbegriffe aus der Tracking-Liste nehmen (GSC-Daten bleiben erhalten)."""
    with _db() as conn:
        return f"{tracking.entfernen(conn, projekt_id, queries)} Begriffe entfernt"


@server.tool()
def tracking_tags(projekt_id: int, queries: list[str], hinzu: list[str] | None = None,
                  weg: list[str] | None = None) -> list[dict]:
    """Tags bei getrackten Begriffen ergänzen (hinzu) oder entfernen (weg)."""
    with _db() as conn:
        tracking.tags_aendern(conn, projekt_id, queries, hinzu, weg)
        return tracking.liste(conn, projekt_id)


# ---------- Search-Console-Zugang ----------

@server.tool()
def gsc_status(projekt_id: int, quelle: str = "gsc") -> dict:
    """Zugang ohne Anfrage prüfen: Schlüsseldatei vorhanden, gespeicherte Property. quelle: gsc | bing.
    Bei gsc auch die Service-Account-Adresse (muss in der Search Console als Nutzer eingetragen sein)."""
    with _db() as conn:
        return gsc_konto.status(conn, projekt_id, quelle)


@server.tool()
def gsc_test(projekt_id: int, quelle: str = "gsc") -> dict:
    """Anmelden (quelle gsc | bing), freigegebene Properties/Websites auflisten und die passende nennen."""
    with _db() as conn:
        return gsc_konto.verbindung_testen(conn, projekt_id, quelle)


@server.tool()
def gsc_property_setzen(projekt_id: int, property: str | None = None, quelle: str = "gsc") -> dict:
    """Property für das Projekt festlegen. gsc: sc-domain:example.de oder https://www.example.de/;
    bing: https://www.example.de/. Leer = beim nächsten Import automatisch suchen."""
    with _db() as conn:
        gsc_konto.property_setzen(conn, projekt_id, property, quelle)
        return gsc_konto.status(conn, projekt_id, quelle)


# ---------- Keyword-Recherche (Phase 5) ----------

@server.tool()
def keyword_recherche_starten(projekt_id: int, seed: str, sprache: str = "de", land: str = "de",
                              warten: bool = False) -> dict:
    """Keyword-Ideen zu einem Hauptbegriff sammeln wie im Semrush Keyword Magic Tool: Google Suggest
    (A–Z, W-Fragen, Zusätze; gedrosselt, 30 Tage Cache) plus eigene GSC-Daten. Läuft ca. 1 Min. im Hintergrund;
    Status mit keyword_recherchen, Ergebnis mit keyword_ideen. Ohne Suchvolumen (fehlt noch)."""
    with _db() as conn:
        return keywords.starten(conn, projekt_id, seed, sprache, land, warten)


@server.tool()
def keyword_recherchen(projekt_id: int) -> list[dict]:
    """Alle Keyword-Recherchen eines Projekts mit Status, Fortschritt (schritte_fertig/schritte_gesamt), Anzahl Ideen."""
    with _db() as conn:
        return keywords.liste(conn, projekt_id)


@server.tool()
def keyword_ideen(recherche_id: int, gruppe: str | None = None, intent: str | None = None, suche: str | None = None,
                  nur_fragen: bool = False, sortierung: str = "impressionen", limit: int = 200) -> dict:
    """Ideen einer Recherche: Keyword, Intent (informational|navigational|kommerziell|transaktional), Gruppe,
    Wörter, Frage, Quellen, eigene GSC-Impressionen/Klicks/Position, volumen (Bing-Impressionen/Monat, falls
    geholt) und trend (Wochenwerte). Dazu Gruppen- und Intent-Zähler.
    sortierung: volumen|impressionen|keyword|woerter|position."""
    with _db() as conn:
        return keywords.ideen(conn, recherche_id, gruppe, intent, suche, nur_fragen, sortierung, limit)


@server.tool()
def keyword_volumen(recherche_id: int, quelle: str = "bing", limit: int = 200, warten: bool = False) -> dict:
    """Suchvolumen für die wichtigsten Ideen einer Recherche holen: Bing-Impressionen pro Monat (kein
    Google-Volumen!) und Wochentrend, 30 Tage Cache. quelle: bing (Bing-Schlüssel nötig) | bing_mock (Testwerte).
    Läuft im Hintergrund; Fortschritt in keyword_recherchen (volumen_status, volumen_fertig/volumen_gesamt)."""
    with _db() as conn:
        return keywords.volumen_starten(conn, recherche_id, quelle, limit, warten)



@server.tool()
def themen_luecke(projekt_id: int, mitbewerber_id: int, limit: int = 100) -> dict:
    """Themen-Lücke zu einem Mitbewerber (beide als Projekt angelegt und gecrawlt): Wortgruppen aus dessen
    Titles/H1, die bei dir in keinem Title/H1 vorkommen, mit Anzahl Texte und Beispiel-URL.
    Ersatz für Keyword Gap ohne Ranking-Daten – zeigt Themen, nicht Traffic."""
    with _db() as conn:
        return luecken.luecke(conn, projekt_id, mitbewerber_id, limit)



# ---------- Core Web Vitals (Labor) ----------

@server.tool()
async def vitals_messen(crawl_id: int | None = None, projekt_id: int | None = None, anzahl: int = 10,
                        geraete: list[str] | None = None) -> dict:
    """Core Web Vitals im Labor messen (echtes Chromium, Drosselung wie Lighthouse mobil/Desktop): LCP, CLS,
    TBT (statt INP), FCP, TTFB, Bytes, Score 0–100 (Lighthouse-Formel ohne Speed Index). Misst die Startseite und
    die Seiten mit der höchsten Link-Stärke. Wartet, bis fertig (ca. 4 s je Seite und Gerät)."""
    def laufen() -> dict:
        with _db() as conn:
            cid = _crawl_id(conn, crawl_id, projekt_id)
            vitals.starten(conn, cid, anzahl, tuple(geraete or ("mobile", "desktop")), warten=True)
            return vitals.ergebnis(conn, cid)
    return await asyncio.to_thread(laufen)  # Playwright-Sync-API nicht im Event-Loop


@server.tool()
def vitals_ergebnis(crawl_id: int | None = None, projekt_id: int | None = None) -> dict:
    """Letzte Core-Web-Vitals-Messung eines Crawls: Werte je Seite/Gerät mit Ampel (gut/mittel/schlecht)
    und Zusammenfassung je Gerät (Median, Score, Anzahl Seiten mit bestandenen Vitals)."""
    with _db() as conn:
        return vitals.ergebnis(conn, _crawl_id(conn, crawl_id, projekt_id))



# ---------- On-Page SEO Checker ----------

@server.tool()
def onpage_pruefen(projekt_id: int, url: str, keyword: str, mitbewerber: list[str] | None = None) -> dict:
    """On-Page SEO Checker wie Semrush: prüft eine Seite gegen ein Keyword (Title, H1, Meta, URL, erste 100 Wörter,
    Häufigkeit, H2/H3, Textlänge, Alt-Texte, Indexierbarkeit, Snippet-Länge, schema.org, Core Web Vitals und interne
    Links aus dem letzten Crawl, Lesbarkeit). Liefert Score 0–100, Ideen nach Priorität, verwandte Begriffe und Fragen
    aus Google Suggest, Begriffe von bis zu 3 Mitbewerber-URLs. Zusätzlich 'ki': KI-Score 0–100 (GEO: Zahlen, Quellen,
    Gliederung, Fragen, Markup, Datum/Autor) mit Prüfungen und Tipps. Dauert ca. 5–25 s."""
    with _db() as conn:
        return onpage.pruefen(conn, projekt_id, url, keyword, mitbewerber or [])


@server.tool()
def onpage_liste(projekt_id: int) -> list[dict]:
    """Bisherige On-Page-Prüfungen eines Projekts (ID, URL, Keyword, Score, Datum). Details mit onpage_ergebnis."""
    with _db() as conn:
        return onpage.liste(conn, projekt_id)


@server.tool()
def onpage_ergebnis(pruefung_id: int) -> dict:
    """Gespeichertes Ergebnis einer On-Page-Prüfung."""
    with _db() as conn:
        return onpage.holen(conn, pruefung_id)
