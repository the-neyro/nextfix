"""REST-API unter /api. Nur dünne Schicht über app.core."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app import berichte, gsc
from app.core import audit, export, gsc_konto, importe, keywords, luecken, onpage, positionen, vitals, projekte, themen, tracking, vergleich
from app.db import sitzung

router = APIRouter(prefix="/api")
Conn = sqlite3.Connection


def _fehler(e: Exception) -> HTTPException:
    status = 404 if "nicht gefunden" in str(e) or "nicht im Crawl" in str(e) else 400
    return HTTPException(status, str(e))


# ---------- Projekte ----------

class ProjektNeu(BaseModel):
    domain: str
    name: str | None = None


@router.get("/projekte")
def projekte_liste(conn: Conn = Depends(sitzung)) -> list[dict]:
    return [p.als_dict() for p in projekte.liste(conn)]


@router.post("/projekte", status_code=201)
def projekt_anlegen(daten: ProjektNeu, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return projekte.anlegen(conn, daten.domain, daten.name).als_dict()
    except projekte.ProjektFehler as e:
        raise _fehler(e)


@router.delete("/projekte/{projekt_id}", status_code=204)
def projekt_loeschen(projekt_id: int, conn: Conn = Depends(sitzung)) -> None:
    try:
        projekte.loeschen(conn, projekt_id)
    except projekte.ProjektFehler as e:
        raise HTTPException(404, str(e))


# ---------- Einstellungen ----------

class Einstellungen(BaseModel):
    start_url: str | None = None
    seitenlimit: int | None = None
    crawl_delay: float | None = None
    user_agent: str | None = None
    robots_beachten: bool | None = None
    quelle: str | None = None
    erlauben: list[str] | None = None             # Pfad-Masken, nur diese crawlen
    sperren: list[str] | None = None              # Pfad-Masken, nicht crawlen
    parameter_entfernen: list[str] | None = None  # URL-Parameter ignorieren ("*" = alle)
    checks_aus: list[str] | None = None           # Check-IDs nicht auswerten
    ladezeit_auto: bool | None = None             # nach jedem Crawl Ladezeit messen
    js_rendern: bool | None = None                # JavaScript ausführen (Chromium)


@router.get("/projekte/{projekt_id}/einstellungen")
def einstellungen_holen(projekt_id: int, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return audit.einstellungen_holen(conn, projekt_id)
    except (projekte.ProjektFehler, audit.AuditFehler) as e:
        raise _fehler(e)


@router.put("/projekte/{projekt_id}/einstellungen")
def einstellungen_setzen(projekt_id: int, daten: Einstellungen, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return audit.einstellungen_setzen(conn, projekt_id, **daten.model_dump(exclude_none=True))
    except (projekte.ProjektFehler, audit.AuditFehler) as e:
        raise _fehler(e)


# ---------- Crawls ----------

@router.post("/projekte/{projekt_id}/crawls", status_code=202)
def crawl_starten(projekt_id: int, warten: bool = False, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return audit.crawl_starten(conn, projekt_id, warten=warten)
    except (projekte.ProjektFehler, audit.AuditFehler) as e:
        raise _fehler(e)


@router.get("/projekte/{projekt_id}/crawls")
def crawls_liste(projekt_id: int, conn: Conn = Depends(sitzung)) -> list[dict]:
    try:
        return audit.crawls_liste(conn, projekt_id)
    except projekte.ProjektFehler as e:
        raise _fehler(e)


@router.get("/crawls/{crawl_id}")
def crawl_holen(crawl_id: int, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return audit.crawl_holen(conn, crawl_id)
    except audit.AuditFehler as e:
        raise _fehler(e)


@router.post("/crawls/{crawl_id}/abbrechen")
def crawl_abbrechen(crawl_id: int, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return audit.crawl_abbrechen(conn, crawl_id)
    except audit.AuditFehler as e:
        raise _fehler(e)


@router.get("/crawls/{crawl_id}/uebersicht")
def uebersicht(crawl_id: int, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return audit.uebersicht(conn, crawl_id)
    except audit.AuditFehler as e:
        raise _fehler(e)


@router.get("/crawls/{crawl_id}/issues")
def issues_liste(crawl_id: int, schwere: str | None = None, kategorie: str | None = None,
                 conn: Conn = Depends(sitzung)) -> list[dict]:
    try:
        return audit.issues_liste(conn, crawl_id, schwere, kategorie)
    except audit.AuditFehler as e:
        raise _fehler(e)


@router.get("/crawls/{crawl_id}/issues/{check_id}")
def issue_details(crawl_id: int, check_id: str, limit: int = 200, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return audit.issue_details(conn, crawl_id, check_id, limit)
    except audit.AuditFehler as e:
        raise _fehler(e)


@router.get("/crawls/{crawl_id}/seiten")
def seiten_liste(crawl_id: int, suche: str | None = None, nur_mit_problemen: bool = False,
                 limit: int = 100, offset: int = 0, conn: Conn = Depends(sitzung)) -> list[dict]:
    try:
        return audit.seiten_liste(conn, crawl_id, suche, nur_mit_problemen, limit, offset)
    except audit.AuditFehler as e:
        raise _fehler(e)


@router.get("/crawls/{crawl_id}/seite")
def seite_details(crawl_id: int, url: str, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return audit.seite_details(conn, crawl_id, url)
    except audit.AuditFehler as e:
        raise _fehler(e)


# ---------- Verlauf und Vergleich ----------

@router.get("/projekte/{projekt_id}/verlauf")
def verlauf(projekt_id: int, conn: Conn = Depends(sitzung)) -> list[dict]:
    try:
        return vergleich.verlauf(conn, projekt_id)
    except projekte.ProjektFehler as e:
        raise _fehler(e)


@router.get("/crawls/{crawl_id}/vergleich")
def crawl_vergleich(crawl_id: int, vorher_id: int | None = None, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return vergleich.vergleich(conn, crawl_id, vorher_id)
    except audit.AuditFehler as e:
        raise _fehler(e)


@router.get("/crawls/{crawl_id}/vergleich/{check_id}")
def treffer_vergleich(crawl_id: int, check_id: str, vorher_id: int | None = None,
                      conn: Conn = Depends(sitzung)) -> dict:
    try:
        return vergleich.treffer_vergleich(conn, crawl_id, check_id, vorher_id)
    except audit.AuditFehler as e:
        raise _fehler(e)


# ---------- Thematische Berichte ----------

@router.get("/crawls/{crawl_id}/themen/{kategorie}")
def thema(crawl_id: int, kategorie: str, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return themen.thema(conn, crawl_id, kategorie)
    except audit.AuditFehler as e:
        raise _fehler(e)


# ---------- CSV-Export ----------

@router.get("/crawls/{crawl_id}/export/bericht.pdf")
def pdf_bericht(crawl_id: int, conn: Conn = Depends(sitzung)) -> Response:
    try:
        inhalt = berichte.site_audit_pdf(conn, crawl_id)
    except audit.AuditFehler as e:
        raise _fehler(e)
    return Response(inhalt, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="site-audit-crawl-{crawl_id}.pdf"'})


@router.get("/crawls/{crawl_id}/export/{art}.csv")
def csv_export(crawl_id: int, art: str, conn: Conn = Depends(sitzung)) -> Response:
    """art: issues | seiten"""
    funktionen = {"issues": export.issues_csv, "seiten": export.seiten_csv}
    if art not in funktionen:
        raise HTTPException(404, f"Unbekannter Export: {art}")
    try:
        inhalt = funktionen[art](conn, crawl_id)
    except audit.AuditFehler as e:
        raise _fehler(e)
    return Response(inhalt, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="crawl-{crawl_id}-{art}.csv"'})


@router.get("/checks")
def checks_katalog() -> list[dict]:
    return audit.checks_katalog()


# ---------- Position Tracking (Search Console) ----------

class GscImport(BaseModel):
    quelle: str = "mock"   # mock | gsc
    tage: int = 90
    warten: bool = False   # True: blockierend, Antwort erst nach dem Import


class AutoImport(BaseModel):
    quelle: str | None = None        # gsc | mock | bing | bing_mock | None = aus
    suchmaschine: str | None = None  # nötig zum Ausschalten: google | bing


def _positionen(funktion, *args, **kwargs):
    try:
        return funktion(*args, **kwargs)
    except (projekte.ProjektFehler, positionen.PositionenFehler, tracking.TrackingFehler, gsc.GscFehler,
            importe.ImportFehler) as e:
        raise _fehler(e)


@router.post("/projekte/{projekt_id}/positionen/import")
def positionen_import(projekt_id: int, daten: GscImport, conn: Conn = Depends(sitzung)) -> dict:
    """Startet einen Import im Hintergrund; Fortschritt unter /positionen/importe."""
    return _positionen(importe.starten, conn, projekt_id, daten.quelle, daten.tage, warten=daten.warten)


@router.get("/projekte/{projekt_id}/positionen/importe")
def positionen_importe(projekt_id: int, limit: int = 10, conn: Conn = Depends(sitzung)) -> list[dict]:
    """Letzte Importe (neueste zuerst) mit Status, Fortschritt (tage_fertig/tage_gesamt) und Fehlern."""
    return _positionen(importe.liste, conn, projekt_id, limit)


@router.get("/projekte/{projekt_id}/positionen/auto")
def auto_import_holen(projekt_id: int, conn: Conn = Depends(sitzung)) -> dict:
    """Je Suchmaschine die Quelle des Auto-Imports oder null."""
    _positionen(projekte.holen, conn, projekt_id)
    return importe.auto_holen(conn, projekt_id)


@router.put("/projekte/{projekt_id}/positionen/auto")
def auto_import_setzen(projekt_id: int, daten: AutoImport, conn: Conn = Depends(sitzung)) -> dict:
    """Täglichen Auto-Import einer Suchmaschine ein- (quelle) oder ausschalten (quelle null + suchmaschine)."""
    return _positionen(importe.auto_setzen, conn, projekt_id, daten.quelle, daten.suchmaschine)


@router.delete("/projekte/{projekt_id}/positionen")
def positionen_loeschen(projekt_id: int, quelle: str | None = None, conn: Conn = Depends(sitzung)) -> dict:
    return {"geloescht": _positionen(positionen.daten_loeschen, conn, projekt_id, quelle)}


@router.get("/projekte/{projekt_id}/positionen")
def positionen_uebersicht(projekt_id: int, tage: int = 28, land: str | None = None, geraet: str | None = None,
                          auswahl: str | None = None, tag: str | None = None, suchmaschine: str = "google",
                          conn: Conn = Depends(sitzung)) -> dict:
    """auswahl: tracking | alle (Standard: Tracking-Liste, falls nicht leer). suchmaschine: google | bing."""
    return _positionen(positionen.uebersicht, conn, projekt_id, tage, land, geraet, auswahl, tag, suchmaschine)


@router.get("/projekte/{projekt_id}/positionen/keywords")
def positionen_keywords(projekt_id: int, tage: int = 28, land: str | None = None, geraet: str | None = None,
                        suche: str | None = None, sortierung: str = "impressionen", auswahl: str | None = None,
                        tag: str | None = None, suchmaschine: str = "google", conn: Conn = Depends(sitzung)) -> dict:
    return _positionen(positionen.keywords, conn, projekt_id, tage, land, geraet, suche, sortierung, auswahl, tag,
                       suchmaschine)


@router.get("/projekte/{projekt_id}/positionen/keywords.csv")
def positionen_keywords_csv(projekt_id: int, tage: int = 28, land: str | None = None, geraet: str | None = None,
                            auswahl: str | None = None, tag: str | None = None, suche: str | None = None,
                            sortierung: str = "impressionen", suchmaschine: str = "google",
                            conn: Conn = Depends(sitzung)) -> Response:
    """Suchbegriffe als CSV (Semikolon, UTF-8 mit BOM, Dezimalkomma), gleiche Filter wie /positionen/keywords."""
    inhalt = _positionen(export.keywords_csv, conn, projekt_id, tage, land, geraet, auswahl, tag, suche, sortierung,
                         suchmaschine)
    return Response(inhalt, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="keywords-projekt-{projekt_id}.csv"'})


@router.get("/projekte/{projekt_id}/positionen/verlauf")
def keyword_verlauf(projekt_id: int, query: str, tage: int = 90, land: str | None = None,
                    geraet: str | None = None, suchmaschine: str = "google", conn: Conn = Depends(sitzung)) -> dict:
    return _positionen(positionen.keyword_verlauf, conn, projekt_id, query, tage, land, geraet, suchmaschine)


# ---------- Tracking-Liste ----------

class TrackingNeu(BaseModel):
    queries: list[str]
    tags: list[str] = []


class TrackingEntfernen(BaseModel):
    queries: list[str]


class TrackingTags(BaseModel):
    queries: list[str]
    hinzu: list[str] = []
    weg: list[str] = []


@router.get("/projekte/{projekt_id}/tracking")
def tracking_liste(projekt_id: int, tag: str | None = None, conn: Conn = Depends(sitzung)) -> dict:
    return {"keywords": _positionen(tracking.liste, conn, projekt_id, tag),
            "tags": tracking.alle_tags(conn, projekt_id)}


@router.post("/projekte/{projekt_id}/tracking")
def tracking_hinzufuegen(projekt_id: int, daten: TrackingNeu, conn: Conn = Depends(sitzung)) -> dict:
    return _positionen(tracking.hinzufuegen, conn, projekt_id, daten.queries, daten.tags)


@router.post("/projekte/{projekt_id}/tracking/entfernen")
def tracking_entfernen(projekt_id: int, daten: TrackingEntfernen, conn: Conn = Depends(sitzung)) -> dict:
    return {"entfernt": _positionen(tracking.entfernen, conn, projekt_id, daten.queries)}


@router.post("/projekte/{projekt_id}/tracking/tags")
def tracking_tags(projekt_id: int, daten: TrackingTags, conn: Conn = Depends(sitzung)) -> dict:
    _positionen(tracking.tags_aendern, conn, projekt_id, daten.queries, daten.hinzu, daten.weg)
    return {"keywords": tracking.liste(conn, projekt_id)}


# ---------- Search-Console-Zugang ----------

class GscProperty(BaseModel):
    property: str | None = None   # leer = automatisch suchen


@router.get("/projekte/{projekt_id}/gsc")
def gsc_status(projekt_id: int, quelle: str = "gsc", conn: Conn = Depends(sitzung)) -> dict:
    """Zugang einer Quelle (gsc | bing): Schlüssel vorhanden? Welche Property? Bei gsc: welche Adresse freigeben?"""
    return _positionen(gsc_konto.status, conn, projekt_id, quelle)


@router.put("/projekte/{projekt_id}/gsc")
def gsc_property_setzen(projekt_id: int, daten: GscProperty, quelle: str = "gsc", conn: Conn = Depends(sitzung)) -> dict:
    _positionen(gsc_konto.property_setzen, conn, projekt_id, daten.property, quelle)
    return gsc_konto.status(conn, projekt_id, quelle)


@router.post("/projekte/{projekt_id}/gsc/test")
def gsc_test(projekt_id: int, quelle: str = "gsc", conn: Conn = Depends(sitzung)) -> dict:
    """Anmeldung testen und freigegebene Properties/Websites auflisten (quelle gsc | bing)."""
    return _positionen(gsc_konto.verbindung_testen, conn, projekt_id, quelle)


# ---------- Keyword-Recherche (Phase 5) ----------

class RechercheNeu(BaseModel):
    seed: str
    sprache: str = "de"
    land: str = "de"
    warten: bool = False


def _kw(funktion, *args, **kwargs):
    try:
        return funktion(*args, **kwargs)
    except (projekte.ProjektFehler, keywords.KeywordFehler) as e:
        raise _fehler(e)


@router.post("/projekte/{projekt_id}/keywords/recherchen", status_code=201)
def recherche_starten(projekt_id: int, daten: RechercheNeu, conn: Conn = Depends(sitzung)) -> dict:
    """Ideen zu einem Hauptbegriff sammeln (Google Suggest + eigene GSC-Daten), läuft im Hintergrund (~1 Min.)."""
    return _kw(keywords.starten, conn, projekt_id, daten.seed, daten.sprache, daten.land, daten.warten)


@router.get("/projekte/{projekt_id}/keywords/recherchen")
def recherchen_liste(projekt_id: int, conn: Conn = Depends(sitzung)) -> list[dict]:
    return _kw(keywords.liste, conn, projekt_id)


@router.get("/keywords/recherchen/{recherche_id}")
def recherche_ideen(recherche_id: int, gruppe: str | None = None, intent: str | None = None,
                    suche: str | None = None, nur_fragen: bool = False, sortierung: str = "impressionen",
                    limit: int = 500, offset: int = 0, conn: Conn = Depends(sitzung)) -> dict:
    """Ideen mit Filtern; dazu Gruppen, Intent-Zähler, Anzahl Fragen. intent: informational|navigational|
    kommerziell|transaktional. sortierung: volumen|impressionen|keyword|woerter|position."""
    return _kw(keywords.ideen, conn, recherche_id, gruppe, intent, suche, nur_fragen, sortierung, limit, offset)


@router.delete("/keywords/recherchen/{recherche_id}", status_code=204)
def recherche_loeschen(recherche_id: int, conn: Conn = Depends(sitzung)) -> None:
    _kw(keywords.loeschen, conn, recherche_id)


@router.get("/keywords/recherchen/{recherche_id}/ideen.csv")
def recherche_csv(recherche_id: int, gruppe: str | None = None, intent: str | None = None,
                  suche: str | None = None, nur_fragen: bool = False, sortierung: str = "impressionen",
                  conn: Conn = Depends(sitzung)) -> Response:
    inhalt = _kw(export.recherche_csv, conn, recherche_id, gruppe=gruppe, intent=intent, suche=suche,
                 nur_fragen=nur_fragen, sortierung=sortierung)
    return Response(inhalt, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="keyword-ideen-{recherche_id}.csv"'})


class VolumenAnfrage(BaseModel):
    quelle: str = "bing"   # bing (Schlüssel nötig) | bing_mock
    limit: int = 200
    warten: bool = False


@router.post("/keywords/recherchen/{recherche_id}/volumen")
def recherche_volumen(recherche_id: int, daten: VolumenAnfrage, conn: Conn = Depends(sitzung)) -> dict:
    """Bing-Impressionen/Monat + Wochentrend für die wichtigsten Ideen holen (Hintergrund)."""
    return _kw(keywords.volumen_starten, conn, recherche_id, daten.quelle, daten.limit, daten.warten)



@router.get("/projekte/{projekt_id}/keywords/luecke")
def themen_luecke(projekt_id: int, mitbewerber_id: int, limit: int = 200, conn: Conn = Depends(sitzung)) -> dict:
    """Themen-Lücke: Wortgruppen aus Titles/H1 des Mitbewerbers (letzter Crawl), die bei dir fehlen."""
    try:
        return luecken.luecke(conn, projekt_id, mitbewerber_id, limit)
    except (projekte.ProjektFehler, luecken.LueckenFehler) as e:
        raise _fehler(e)



# ---------- Core Web Vitals (Labor) ----------

class VitalsAnfrage(BaseModel):
    anzahl: int = 10                       # Seiten (Startseite + stärkste interne Seiten)
    geraete: list[str] = ["mobile", "desktop"]
    warten: bool = False


@router.post("/crawls/{crawl_id}/vitals")
def vitals_starten(crawl_id: int, daten: VitalsAnfrage, conn: Conn = Depends(sitzung)) -> dict:
    """LCP, CLS, TBT, FCP, TTFB mit echtem Chromium messen (gedrosselt wie Lighthouse). Hintergrund, ca. 4 s je Messung."""
    try:
        return vitals.starten(conn, crawl_id, daten.anzahl, tuple(daten.geraete), daten.warten)
    except (audit.AuditFehler, vitals.VitalsFehler) as e:
        raise _fehler(e)


@router.get("/crawls/{crawl_id}/vitals")
def vitals_ergebnis(crawl_id: int, conn: Conn = Depends(sitzung)) -> dict:
    try:
        return vitals.ergebnis(conn, crawl_id)
    except audit.AuditFehler as e:
        raise _fehler(e)



# ---------- On-Page SEO Checker ----------

class OnpageAnfrage(BaseModel):
    url: str
    keyword: str
    mitbewerber: list[str] = []   # bis zu 3 URLs, z. B. aus der eigenen Google-Suche
    mit_suggest: bool = True


def _op(funktion, *args, **kwargs):
    try:
        return funktion(*args, **kwargs)
    except (projekte.ProjektFehler, onpage.OnpageFehler) as e:
        raise _fehler(e)


@router.post("/projekte/{projekt_id}/onpage", status_code=201)
def onpage_pruefen(projekt_id: int, daten: OnpageAnfrage, conn: Conn = Depends(sitzung)) -> dict:
    """Seite gegen Keyword prüfen: Score, Prüfungen, Ideen (mit Priorität), verwandte Begriffe, Fragen, Mitbewerber.
    Dauert ca. 5–25 s (Suggest gedrosselt, beim zweiten Mal aus dem Cache)."""
    return _op(onpage.pruefen, conn, projekt_id, daten.url, daten.keyword, daten.mitbewerber, daten.mit_suggest)


@router.get("/projekte/{projekt_id}/onpage")
def onpage_liste(projekt_id: int, conn: Conn = Depends(sitzung)) -> list[dict]:
    return _op(onpage.liste, conn, projekt_id)


@router.get("/onpage/{pruefung_id}")
def onpage_holen(pruefung_id: int, conn: Conn = Depends(sitzung)) -> dict:
    return _op(onpage.holen, conn, pruefung_id)
