"""Web-UI (Jinja + HTMX). Start: .venv/bin/uvicorn app.web:app --reload"""

import html
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import checks, gsc
from app.api import router as api_router
from app.core import audit, aufgaben, ausblenden, export, teilnoten, gsc_konto, importe, keywords, luecken, onpage, positionen, vitals, projekte, themen, tracking, vergleich
from app.db import sitzung, verbinden
from app.gsc.laender import land_name



@asynccontextmanager
async def lebenszyklus(_app: FastAPI):
    """Beim Start den Auto-Import-Planer anwerfen (aus mit SEO_PLANER=0)."""
    if os.environ.get("SEO_PLANER", "1") != "0":
        importe.planer_starten()
    yield


app = FastAPI(title="Nextfix", lifespan=lebenszyklus)
app.include_router(api_router)
templates = Jinja2Templates(directory=Path(__file__).with_name("templates"))
app.mount("/static", StaticFiles(directory=Path(__file__).with_name("static")), name="static")
templates.env.filters["land_name"] = land_name
templates.env.globals["sparkline"] = lambda werte: _linie(werte, 60, 16)
Conn = sqlite3.Connection


def _navi(projekt_id: int | None) -> dict:
    """Daten für die Seitenleiste: alle Projekte, letzte fertige Prüfung, Zahl offener Aufgaben (ohne Feinschliff)."""
    conn = verbinden()
    try:
        daten = {"projekte": projekte.liste(conn), "crawl_id": None, "aufgaben": None}
        if projekt_id:
            daten["crawl_id"] = audit.letzter_crawl_id(conn, projekt_id)
            if daten["crawl_id"]:
                daten["aufgaben"] = sum(1 for i in audit.issues_liste(conn, daten["crawl_id"])
                                        if i["schwere"] != "notice" and i["anzahl"])
        return daten
    finally:
        conn.close()


templates.env.globals["navi"] = _navi


def _zahl(wert, stellen: int = 0) -> str:
    """Deutsche Schreibweise: 1.234,5"""
    if wert is None:
        return "–"
    return f"{wert:,.{stellen}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


templates.env.filters["zahl"] = _zahl


def _datum(wert: str | None, mit_zeit: bool = False) -> str:
    """'2026-10-15 18:05:06' (UTC aus SQLite) → '15.10.2026' bzw. '15.10.2026, 20:05' in Ortszeit."""
    if not wert:
        return "–"
    try:
        t = datetime.fromisoformat(str(wert).replace("Z", "")).replace(tzinfo=timezone.utc).astimezone()
    except ValueError:
        return str(wert)
    return t.strftime("%d.%m.%Y, %H:%M" if mit_zeit and " " in str(wert) else "%d.%m.%Y")


templates.env.filters["datum"] = _datum
templates.env.filters["pfad"] = lambda url: (urlsplit(url).path or "/") + (f"?{urlsplit(url).query}" if urlsplit(url).query else "")
templates.env.globals["STUFE"] = {"error": ("dringend", "Dringend"), "warning": ("wichtig", "Wichtig"),
                                  "notice": ("feinschliff", "Feinschliff")}


def _seite(request: Request, vorlage: str, **daten) -> HTMLResponse:
    return templates.TemplateResponse(request, vorlage, daten)


def _projekt(conn: Conn, projekt_id: int) -> projekte.Projekt:
    try:
        return projekte.holen(conn, projekt_id)
    except projekte.ProjektFehler as e:
        raise HTTPException(404, str(e))


def _crawl(conn: Conn, crawl_id: int) -> dict:
    try:
        return audit.crawl_holen(conn, crawl_id)
    except audit.AuditFehler as e:
        raise HTTPException(404, str(e))


def _aktueller_crawl(conn: Conn, projekt_id: int) -> dict | None:
    crawl_id = audit.letzter_crawl_id(conn, projekt_id, nur_fertige=False)
    return audit.crawl_holen(conn, crawl_id) if crawl_id else None


# ---------- Projekte ----------

def _projekt_karten(conn: Conn) -> list[dict]:
    """Projekte mit Stand der letzten Prüfung (Zustand, Datum, offene Aufgaben)."""
    karten = []
    for p in projekte.liste(conn):
        crawl_id = audit.letzter_crawl_id(conn, p.id)
        karte = {"p": p, "health": None, "datum": None, "aufgaben": None}
        if crawl_id:
            c = audit.crawl_holen(conn, crawl_id)
            karte.update(health=c["health"] if c["health"] is not None else audit._health(conn, crawl_id),
                         datum=c["beendet_am"],
                         aufgaben=sum(1 for i in audit.issues_liste(conn, crawl_id) if i["schwere"] != "notice"))
        karten.append(karte)
    return karten


@app.get("/", response_class=HTMLResponse)
def startseite(request: Request, conn: Conn = Depends(sitzung)):
    return _seite(request, "index.html", karten=_projekt_karten(conn))


@app.post("/projekte", response_class=HTMLResponse)
def projekt_anlegen(request: Request, domain: str = Form(...), name: str = Form(""),
                    conn: Conn = Depends(sitzung)):
    """HTMX: legt Projekt an und liefert die aktualisierte Liste zurück."""
    fehler = None
    try:
        projekte.anlegen(conn, domain, name)
    except projekte.ProjektFehler as e:
        fehler = str(e)
    return _seite(request, "_projektliste.html", karten=_projekt_karten(conn), fehler=fehler)


@app.get("/projekte/{projekt_id}", response_class=HTMLResponse)
def projekt_seite(request: Request, projekt_id: int, conn: Conn = Depends(sitzung)):
    projekt = _projekt(conn, projekt_id)
    fertig_id = audit.letzter_crawl_id(conn, projekt_id)
    daten = {"projekt": projekt, "aktuell": _aktueller_crawl(conn, projekt_id), "ue": None}
    if fertig_id:
        a = aufgaben.liste(conn, fertig_id)
        daten.update(ue=audit.uebersicht(conn, fertig_id), aufg=a, noten=teilnoten.liste(conn, projekt_id, fertig_id),
                     vorher_health=audit._health(conn, a["vorher_id"]) if a["vorher_id"] else None)
    return _seite(request, "projekt.html", **daten)


@app.get("/projekte/{projekt_id}/einstellungen", response_class=HTMLResponse)
def einstellungen_seite(request: Request, projekt_id: int, conn: Conn = Depends(sitzung)):
    return _seite(request, "einstellungen.html", projekt=_projekt(conn, projekt_id),
                  e=audit.einstellungen_holen(conn, projekt_id), katalog=audit.checks_katalog(),
                  kategorien=checks.KATEGORIEN)


@app.post("/projekte/{projekt_id}/einstellungen", response_class=HTMLResponse)
def einstellungen_speichern(projekt_id: int, start_url: str = Form(...), seitenlimit: int = Form(...),
                            crawl_delay: float = Form(...), user_agent: str = Form(...),
                            robots_beachten: int = Form(...), quelle: str = Form("website"),
                            erlauben: str = Form(""), sperren: str = Form(""), parameter_entfernen: str = Form(""),
                            checks_aus: list[str] = Form([]), ladezeit_auto: str = Form(""),
                            conn: Conn = Depends(sitzung)):
    _projekt(conn, projekt_id)
    try:
        audit.einstellungen_setzen(conn, projekt_id, start_url=start_url, seitenlimit=seitenlimit,
                                   crawl_delay=crawl_delay, user_agent=user_agent,
                                   robots_beachten=bool(robots_beachten), quelle=quelle, erlauben=erlauben,
                                   sperren=sperren, parameter_entfernen=parameter_entfernen, checks_aus=checks_aus,
                                   ladezeit_auto=bool(ladezeit_auto))
    except audit.AuditFehler as e:
        return HTMLResponse(f'<span class="fehler">{html.escape(str(e))}</span>')
    return HTMLResponse('<span class="gut">Gespeichert</span>')


# ---------- Crawl steuern (HTMX-Fragmente) ----------

def _status_fragment(request: Request, conn: Conn, projekt_id: int, fehler: str | None = None):
    return _seite(request, "_crawl_status.html", projekt=_projekt(conn, projekt_id),
                  aktuell=_aktueller_crawl(conn, projekt_id), fehler=fehler)


@app.post("/projekte/{projekt_id}/crawls", response_class=HTMLResponse)
def crawl_starten(request: Request, projekt_id: int, conn: Conn = Depends(sitzung)):
    try:
        audit.crawl_starten(conn, projekt_id)
    except audit.AuditFehler as e:
        return _status_fragment(request, conn, projekt_id, str(e))
    return _status_fragment(request, conn, projekt_id)


@app.get("/projekte/{projekt_id}/status", response_class=HTMLResponse)
def crawl_status(request: Request, projekt_id: int, conn: Conn = Depends(sitzung)):
    antwort = _status_fragment(request, conn, projekt_id)
    aktuell = _aktueller_crawl(conn, projekt_id)
    if aktuell and aktuell["status"] != "laeuft":
        antwort.headers["HX-Refresh"] = "true"  # fertig → ganze Seite mit Übersicht neu laden
    return antwort


@app.post("/crawls/{crawl_id}/abbrechen", response_class=HTMLResponse)
def crawl_abbrechen(request: Request, crawl_id: int, conn: Conn = Depends(sitzung)):
    crawl = _crawl(conn, crawl_id)
    fehler = None
    try:
        audit.crawl_abbrechen(conn, crawl_id)
    except audit.AuditFehler as e:
        fehler = str(e)
    return _status_fragment(request, conn, crawl["projekt_id"], fehler)


# ---------- Auswertung ----------

@app.get("/crawls/{crawl_id}/issues", response_class=HTMLResponse)
def issues_seite(request: Request, crawl_id: int, schwere: str = "", kategorie: str = "",
                 conn: Conn = Depends(sitzung)):
    crawl = _crawl(conn, crawl_id)
    return _seite(request, "issues.html", crawl=crawl, projekt=_projekt(conn, crawl["projekt_id"]),
                  issues=audit.issues_liste(conn, crawl_id, schwere or None, kategorie or None),
                  schwere=schwere, kategorie=kategorie, ausgeblendet=ausblenden.liste(conn, crawl["projekt_id"]),
                  schweregrade=checks.SCHWEREGRADE, kategorien=checks.KATEGORIEN)


def _pfad_gruppe(url: str) -> str:
    """Erster Pfadteil als Gruppe (/glossary/…) – oft steckt ein gemeinsames Template dahinter."""
    teile = urlsplit(url).path.strip("/").split("/")
    return f"/{teile[0]}/" if len(teile) > 1 else "/"


@app.get("/crawls/{crawl_id}/issues/{check_id}/seite", response_class=HTMLResponse)
def issue_seite(request: Request, crawl_id: int, check_id: str, gruppe: str = "", conn: Conn = Depends(sitzung)):
    """Ein Problem auf eigener Seite: warum, wie beheben, Fundstellen nach Pfad gruppiert."""
    crawl = _crawl(conn, crawl_id)
    try:
        d = audit.issue_details(conn, crawl_id, check_id, limit=2000)
    except audit.AuditFehler as e:
        raise HTTPException(404, str(e))
    a = next((x for x in (lambda l: l["aufgaben"] + l["feinschliff"])(aufgaben.liste(conn, crawl_id))
              if x["id"] == check_id), None)
    gruppen: dict[str, int] = {}
    for t in d["treffer"]:
        if t["url"]:
            gruppen[_pfad_gruppe(t["url"])] = gruppen.get(_pfad_gruppe(t["url"]), 0) + 1
    treffer = [t for t in d["treffer"] if not gruppe or (t["url"] and _pfad_gruppe(t["url"]) == gruppe)]
    return _seite(request, "issue.html", crawl=crawl, projekt=_projekt(conn, crawl["projekt_id"]), d=d, a=a,
                  gruppen=sorted(gruppen.items(), key=lambda g: -g[1]) if len(gruppen) > 1 else [],
                  gruppe=gruppe, treffer=treffer)


@app.get("/crawls/{crawl_id}/issues/{check_id}", response_class=HTMLResponse)
def issue_treffer(request: Request, crawl_id: int, check_id: str, conn: Conn = Depends(sitzung)):
    try:
        d = audit.issue_details(conn, crawl_id, check_id)
    except audit.AuditFehler as e:
        raise HTTPException(404, str(e))
    return _seite(request, "_issue_treffer.html", d=d, crawl_id=crawl_id)


def _zurueck(zurueck: str, projekt_id: int) -> str:
    """Nur interne Ziele zulassen (kein Sprung auf fremde Seiten)."""
    return zurueck if zurueck.startswith(("/crawls/", "/projekte/")) else f"/projekte/{projekt_id}"


@app.post("/projekte/{projekt_id}/ausblenden")
def ausblenden_speichern(projekt_id: int, check_id: str = Form(""), url: str = Form(""), grund: str = Form(""),
                         zurueck: str = Form(""), conn: Conn = Depends(sitzung)):
    """„Bewusst so“: Problem, Seite oder Fundstelle ausblenden."""
    try:
        ausblenden.ausblenden(conn, projekt_id, check_id, url, grund)
    except (ausblenden.AusblendenFehler, projekte.ProjektFehler) as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(_zurueck(zurueck, projekt_id), status_code=303)


@app.post("/projekte/{projekt_id}/einblenden")
def einblenden(projekt_id: int, ausblendung_id: int = Form(...), zurueck: str = Form(""),
               conn: Conn = Depends(sitzung)):
    try:
        ausblenden.einblenden(conn, projekt_id, ausblendung_id)
    except ausblenden.AusblendenFehler as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(_zurueck(zurueck, projekt_id), status_code=303)


@app.get("/crawls/{crawl_id}/seiten", response_class=HTMLResponse)
def seiten_seite(request: Request, crawl_id: int, suche: str = "", nur_mit_problemen: str = "",
                 offset: int = 0, conn: Conn = Depends(sitzung)):
    crawl = _crawl(conn, crawl_id)
    limit = 100
    return _seite(request, "seiten.html", crawl=crawl, projekt=_projekt(conn, crawl["projekt_id"]),
                  seiten=audit.seiten_liste(conn, crawl_id, suche or None, bool(nur_mit_problemen), limit, offset),
                  suche=suche, nur_mit_problemen=bool(nur_mit_problemen), limit=limit, offset=offset)


@app.get("/crawls/{crawl_id}/seite", response_class=HTMLResponse)
def seite_details(request: Request, crawl_id: int, url: str, conn: Conn = Depends(sitzung)):
    crawl = _crawl(conn, crawl_id)
    try:
        s = audit.seite_details(conn, crawl_id, url)
    except audit.AuditFehler as e:
        raise HTTPException(404, str(e))
    return _seite(request, "seite.html", crawl=crawl, projekt=_projekt(conn, crawl["projekt_id"]), s=s)


# ---------- Verlauf und Vergleich ----------

@app.get("/crawls/{crawl_id}/vergleich", response_class=HTMLResponse)
def vergleich_seite(request: Request, crawl_id: int, conn: Conn = Depends(sitzung)):
    crawl = _crawl(conn, crawl_id)
    try:
        v = vergleich.vergleich(conn, crawl_id)
    except audit.AuditFehler:
        v = None  # erster Crawl des Projekts
    return _seite(request, "vergleich.html", crawl=crawl, projekt=_projekt(conn, crawl["projekt_id"]),
                  verlauf=vergleich.verlauf(conn, crawl["projekt_id"]), v=v)


@app.get("/crawls/{crawl_id}/vergleich/{check_id}", response_class=HTMLResponse)
def vergleich_treffer(request: Request, crawl_id: int, check_id: str, vorher_id: int | None = None,
                      conn: Conn = Depends(sitzung)):
    try:
        t = vergleich.treffer_vergleich(conn, crawl_id, check_id, vorher_id)
    except audit.AuditFehler as e:
        raise HTTPException(404, str(e))
    return _seite(request, "_vergleich_treffer.html", t=t)


# ---------- Thematische Berichte ----------

@app.get("/crawls/{crawl_id}/themen/{kategorie}", response_class=HTMLResponse)
def thema_seite(request: Request, crawl_id: int, kategorie: str, conn: Conn = Depends(sitzung)):
    crawl = _crawl(conn, crawl_id)
    try:
        t = themen.thema(conn, crawl_id, kategorie)
    except audit.AuditFehler as e:
        raise HTTPException(404, str(e))
    return _seite(request, "thema.html", crawl=crawl, projekt=_projekt(conn, crawl["projekt_id"]), t=t,
                  kategorien=checks.KATEGORIEN)


# ---------- Position Tracking ----------

def _linie(werte: list[float], breite: int = 600, hoehe: int = 120, umgekehrt: bool = False) -> str:
    """Punkte für eine SVG-Polyline. umgekehrt: kleine Werte oben (Positionen)."""
    if not werte:
        return ""
    unten, oben = min(werte), max(werte)
    spanne = (oben - unten) or 1
    schritt = breite / max(len(werte) - 1, 1)
    punkte = []
    for i, w in enumerate(werte):
        anteil = (w - unten) / spanne
        y = anteil if umgekehrt else 1 - anteil
        punkte.append(f"{i * schritt:.1f},{4 + y * (hoehe - 8):.1f}")
    return " ".join(punkte)


@app.get("/projekte/{projekt_id}/positionen", response_class=HTMLResponse)
def positionen_seite(request: Request, projekt_id: int, tage: int = 28, geraet: str = "", land: str = "",
                     suchmaschine: str = "google",
                     sortierung: str = "impressionen", suche: str = "", auswahl: str = "", tag: str = "",
                     conn: Conn = Depends(sitzung)):
    projekt = _projekt(conn, projekt_id)
    daten = dict(projekt=projekt, bestand=positionen.bestand(conn, projekt_id), tage=tage, geraet=geraet,
                 sortierung=sortierung, suche=suche, tag=tag, land=land, suchmaschine=suchmaschine, u=None, kw=None, fehler=None,
                 zugang={q: gsc_konto.status(conn, projekt_id, q) for q in gsc.MIT_ZUGANG},
                 imp=importe.letzter(conn, projekt_id), auto=importe.auto_holen(conn, projekt_id),
                 getrackt=len(tracking.liste(conn, projekt_id)), tags=tracking.alle_tags(conn, projekt_id),
                 zurueck=request.url.path + (f"?{request.url.query}" if request.url.query else ""))
    if daten["bestand"]:
        try:
            daten["u"] = positionen.uebersicht(conn, projekt_id, tage, land or None, geraet or None, auswahl or None,
                                               tag or None, suchmaschine)
            daten["kw"] = positionen.keywords(conn, projekt_id, tage, land or None, geraet or None, suche or None,
                                              sortierung, auswahl or None, tag or None, suchmaschine)["keywords"]
        except positionen.PositionenFehler as e:
            daten["fehler"] = str(e)
        if daten["u"]:
            t = daten["u"]["tage"]
            daten["linie_klicks"] = _linie([x["klicks"] for x in t])
            daten["linie_position"] = _linie([x["position"] for x in t], umgekehrt=True)
    return _seite(request, "positionen.html", **daten)


@app.post("/projekte/{projekt_id}/positionen/import", response_class=HTMLResponse)
def positionen_import(request: Request, projekt_id: int, quelle: str = Form("mock"), tage: int = Form(90),
                      conn: Conn = Depends(sitzung)):
    """HTMX: startet den Import im Hintergrund und liefert den Status-Block (pollt selbst weiter)."""
    _projekt(conn, projekt_id)
    fehler = None
    try:
        importe.starten(conn, projekt_id, quelle, tage)
    except importe.ImportFehler as e:
        fehler = str(e)
    return _import_status(request, conn, projekt_id, fehler)


def _import_status(request: Request, conn: Conn, projekt_id: int, fehler: str | None = None):
    return _seite(request, "_import_status.html", projekt=_projekt(conn, projekt_id),
                  imp=importe.letzter(conn, projekt_id), fehler=fehler)


@app.get("/projekte/{projekt_id}/positionen/import-status", response_class=HTMLResponse)
def import_status(request: Request, projekt_id: int, conn: Conn = Depends(sitzung)):
    antwort = _import_status(request, conn, projekt_id)
    imp = importe.letzter(conn, projekt_id)
    if imp and imp["status"] != "laeuft":
        antwort.headers["HX-Refresh"] = "true"  # fertig → Seite mit neuen Daten laden
    return antwort


@app.post("/projekte/{projekt_id}/positionen/auto", response_class=HTMLResponse)
def auto_import(projekt_id: int, quelle: str = Form(""), suchmaschine: str = Form(""), conn: Conn = Depends(sitzung)):
    _projekt(conn, projekt_id)
    try:
        stand = importe.auto_setzen(conn, projekt_id, quelle or None, suchmaschine or None)
    except importe.ImportFehler as e:
        return HTMLResponse(f'<span class="fehler">{html.escape(str(e))}</span>')
    namen = {"gsc": "Search Console", "mock": "Testdaten", "bing": "Bing Webmaster", "bing_mock": "Testdaten"}
    teile = [f"{m.capitalize()}: {namen[q] if q else 'aus'}" for m, q in stand.items()]
    return HTMLResponse(f'<span class="gut">Auto-Import · {" · ".join(teile)}</span>')


@app.post("/projekte/{projekt_id}/gsc", response_class=HTMLResponse)
def gsc_property_speichern(projekt_id: int, property: str = Form(""), quelle: str = Form("gsc"),
                           conn: Conn = Depends(sitzung)):
    _projekt(conn, projekt_id)
    try:
        prop = gsc_konto.property_setzen(conn, projekt_id, property, quelle)
    except gsc.GscFehler as e:
        return HTMLResponse(f'<span class="fehler">{html.escape(str(e))}</span>')
    return HTMLResponse(f'<span class="gut">Gespeichert: {html.escape(prop or "automatisch suchen")}</span>')


@app.post("/projekte/{projekt_id}/gsc/test", response_class=HTMLResponse)
def gsc_test(request: Request, projekt_id: int, quelle: str = "gsc", conn: Conn = Depends(sitzung)):
    _projekt(conn, projekt_id)
    try:
        t = gsc_konto.verbindung_testen(conn, projekt_id, quelle)
    except gsc.GscFehler as e:
        raise HTTPException(400, str(e))
    return _seite(request, "_gsc_test.html", t=t)


@app.post("/projekte/{projekt_id}/tracking")
def tracking_aendern(projekt_id: int, aktion: str = Form(...), query: list[str] = Form([]), neu: str = Form(""),
                     tags: str = Form(""), zurueck: str = Form(""), conn: Conn = Depends(sitzung)):
    """Formular der Positionen-Seite: Auswahl aufnehmen/entfernen, Tag setzen/entfernen, Begriffe eintippen."""
    _projekt(conn, projekt_id)
    try:
        if aktion == "neu":
            tracking.hinzufuegen(conn, projekt_id, neu, tags)
        elif aktion == "hinzufuegen":
            tracking.hinzufuegen(conn, projekt_id, query, tags)
        elif aktion == "entfernen":
            tracking.entfernen(conn, projekt_id, query)
        elif aktion == "tag_weg":
            tracking.tags_aendern(conn, projekt_id, query, weg=tags)
        else:
            raise HTTPException(400, f"Unbekannte Aktion: {aktion}")
    except tracking.TrackingFehler as e:
        raise HTTPException(400, str(e))
    ziel = zurueck if zurueck.startswith(("/projekte/", "/recherchen/")) else f"/projekte/{projekt_id}/positionen"
    return RedirectResponse(ziel, status_code=303)


@app.get("/projekte/{projekt_id}/positionen/verlauf", response_class=HTMLResponse)
def keyword_verlauf(request: Request, projekt_id: int, query: str, tage: int = 90, geraet: str = "", land: str = "",
                    suchmaschine: str = "google", conn: Conn = Depends(sitzung)):
    try:
        v = positionen.keyword_verlauf(conn, projekt_id, query, tage, land or None, geraet or None, suchmaschine)
    except positionen.PositionenFehler as e:
        raise HTTPException(404, str(e))
    return _seite(request, "_keyword_verlauf.html", v=v,
                  linie=_linie([t["position"] for t in v["tage"]], umgekehrt=True),
                  beste=min(t["position"] for t in v["tage"]), schlechteste=max(t["position"] for t in v["tage"]))


@app.get("/projekte/{projekt_id}/positionen/keywords.csv")
def keywords_csv(projekt_id: int, tage: int = 28, land: str = "", geraet: str = "", auswahl: str = "",
                 tag: str = "", suche: str = "", sortierung: str = "impressionen", suchmaschine: str = "google",
                 conn: Conn = Depends(sitzung)):
    """CSV mit denselben Filtern wie die Tabelle auf der Seite."""
    projekt = _projekt(conn, projekt_id)
    try:
        inhalt = export.keywords_csv(conn, projekt_id, tage, land or None, geraet or None, auswahl or None,
                                     tag or None, suche or None, sortierung, suchmaschine)
    except positionen.PositionenFehler as e:
        raise HTTPException(400, str(e))
    name = f"keywords-{suchmaschine}-{projekt.domain}-{tage}-tage.csv"
    return Response(inhalt, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------- Keyword-Recherche (Phase 5) ----------

def _recherchen_fragment(request: Request, conn: Conn, projekt_id: int, fehler: str | None = None):
    return _seite(request, "_recherchen.html", projekt=_projekt(conn, projekt_id),
                  recherchen=keywords.liste(conn, projekt_id), fehler=fehler)


@app.get("/projekte/{projekt_id}/keywords", response_class=HTMLResponse)
def keywords_seite(request: Request, projekt_id: int, conn: Conn = Depends(sitzung)):
    return _seite(request, "keywords.html", projekt=_projekt(conn, projekt_id),
                  recherchen=keywords.liste(conn, projekt_id), fehler=None,
                  andere=[p for p in projekte.liste(conn) if p.id != projekt_id])


@app.post("/projekte/{projekt_id}/keywords", response_class=HTMLResponse)
def recherche_starten(request: Request, projekt_id: int, seed: str = Form(...), conn: Conn = Depends(sitzung)):
    _projekt(conn, projekt_id)
    fehler = None
    try:
        keywords.starten(conn, projekt_id, seed)
    except keywords.KeywordFehler as e:
        fehler = str(e)
    return _recherchen_fragment(request, conn, projekt_id, fehler)


@app.get("/projekte/{projekt_id}/keywords/liste", response_class=HTMLResponse)
def recherchen_liste(request: Request, projekt_id: int, conn: Conn = Depends(sitzung)):
    return _recherchen_fragment(request, conn, projekt_id)


@app.get("/recherchen/{recherche_id}", response_class=HTMLResponse)
def recherche_seite(request: Request, recherche_id: int, gruppe: str = "", intent: str = "", suche: str = "",
                    nur_fragen: str = "", sortierung: str = "impressionen", offset: int = 0,
                    conn: Conn = Depends(sitzung)):
    try:
        d = keywords.ideen(conn, recherche_id, gruppe or None, intent or None, suche or None, bool(nur_fragen),
                           sortierung, 200, offset)
    except keywords.KeywordFehler as e:
        raise HTTPException(404 if "nicht gefunden" in str(e) else 400, str(e))
    getrackt = {k["query"] for k in tracking.liste(conn, d["recherche"]["projekt_id"])}
    return _seite(request, "recherche.html", d=d, projekt=_projekt(conn, d["recherche"]["projekt_id"]),
                  bing_da=gsc_konto.status(conn, d["recherche"]["projekt_id"], "bing")["schluessel_da"],
                  gruppe=gruppe, intent=intent, suche=suche, nur_fragen=bool(nur_fragen), sortierung=sortierung,
                  offset=offset, getrackt=getrackt,
                  zurueck=request.url.path + (f"?{request.url.query}" if request.url.query else ""))



@app.post("/recherchen/{recherche_id}/volumen", response_class=HTMLResponse)
def recherche_volumen(request: Request, recherche_id: int, quelle: str = Form("bing"), conn: Conn = Depends(sitzung)):
    fehler = None
    try:
        keywords.volumen_starten(conn, recherche_id, quelle)
    except keywords.KeywordFehler as e:
        fehler = str(e)
    return _seite(request, "_volumen_status.html", r=keywords.holen(conn, recherche_id), fehler=fehler)


@app.get("/recherchen/{recherche_id}/volumen-status", response_class=HTMLResponse)
def volumen_status(request: Request, recherche_id: int, conn: Conn = Depends(sitzung)):
    try:
        r = keywords.holen(conn, recherche_id)
    except keywords.KeywordFehler as e:
        raise HTTPException(404, str(e))
    antwort = _seite(request, "_volumen_status.html", r=r, fehler=None)
    if r["volumen_status"] != "laeuft":
        antwort.headers["HX-Refresh"] = "true"
    return antwort



@app.post("/projekte/{projekt_id}/keywords/neu")
def recherche_aus_formular(projekt_id: int, seed: str = Form(...), conn: Conn = Depends(sitzung)):
    """Normales Formular (z. B. aus der Themen-Lücke): Recherche starten, zurück zur Keyword-Seite."""
    _projekt(conn, projekt_id)
    try:
        keywords.starten(conn, projekt_id, seed)
    except keywords.KeywordFehler as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(f"/projekte/{projekt_id}/keywords", status_code=303)


@app.get("/projekte/{projekt_id}/keywords/luecke", response_class=HTMLResponse)
def luecke_seite(request: Request, projekt_id: int, mitbewerber_id: int, conn: Conn = Depends(sitzung)):
    projekt = _projekt(conn, projekt_id)
    try:
        l = luecken.luecke(conn, projekt_id, mitbewerber_id)
    except luecken.LueckenFehler as e:
        l, fehler = None, str(e)
    except projekte.ProjektFehler as e:
        raise HTTPException(404, str(e))
    else:
        fehler = None
    return _seite(request, "luecke.html", projekt=projekt, l=l, fehler=fehler)



# ---------- Core Web Vitals ----------

@app.get("/crawls/{crawl_id}/vitals", response_class=HTMLResponse)
def vitals_seite(request: Request, crawl_id: int, conn: Conn = Depends(sitzung)):
    crawl = _crawl(conn, crawl_id)
    return _seite(request, "vitals.html", crawl=crawl, projekt=_projekt(conn, crawl["projekt_id"]),
                  v=vitals.ergebnis(conn, crawl_id), fehler=None)


@app.post("/crawls/{crawl_id}/vitals", response_class=HTMLResponse)
def vitals_starten(request: Request, crawl_id: int, anzahl: int = Form(10), conn: Conn = Depends(sitzung)):
    crawl = _crawl(conn, crawl_id)
    fehler = None
    try:
        vitals.starten(conn, crawl_id, anzahl)
    except vitals.VitalsFehler as e:
        fehler = str(e)
    return _seite(request, "_vitals_status.html", crawl=crawl, lauf=vitals.ergebnis(conn, crawl_id)["lauf"], fehler=fehler)


@app.get("/crawls/{crawl_id}/vitals-status", response_class=HTMLResponse)
def vitals_status(request: Request, crawl_id: int, conn: Conn = Depends(sitzung)):
    crawl = _crawl(conn, crawl_id)
    lauf = vitals.ergebnis(conn, crawl_id)["lauf"]
    antwort = _seite(request, "_vitals_status.html", crawl=crawl, lauf=lauf, fehler=None)
    if lauf and lauf["status"] != "laeuft":
        antwort.headers["HX-Refresh"] = "true"
    return antwort



# ---------- On-Page SEO Checker ----------

@app.get("/projekte/{projekt_id}/onpage", response_class=HTMLResponse)
def onpage_seite(request: Request, projekt_id: int, url: str = "", keyword: str = "", conn: Conn = Depends(sitzung)):
    projekt = _projekt(conn, projekt_id)
    crawl_id = audit.letzter_crawl_id(conn, projekt_id)
    seiten = [z["url"] for z in conn.execute(
        "SELECT url FROM seiten WHERE crawl_id = ? AND status_code = 200 AND woerter IS NOT NULL"
        " ORDER BY COALESCE(link_rank, 0) DESC LIMIT 300", (crawl_id,))] if crawl_id else []
    return _seite(request, "onpage.html", projekt=projekt, seiten=seiten, liste=onpage.liste(conn, projekt_id),
                  url=url or f"https://{projekt.domain}/", keyword=keyword, r=None)


@app.post("/projekte/{projekt_id}/onpage", response_class=HTMLResponse)
def onpage_pruefen(request: Request, projekt_id: int, url: str = Form(...), keyword: str = Form(...),
                   mitbewerber: str = Form(""), conn: Conn = Depends(sitzung)):
    _projekt(conn, projekt_id)
    try:
        r = onpage.pruefen(conn, projekt_id, url, keyword, mitbewerber.splitlines())
    except onpage.OnpageFehler as e:
        return HTMLResponse(f'<div class="karte fehler">{html.escape(str(e))}</div>')
    return _seite(request, "_onpage_ergebnis.html", r=r)


@app.get("/onpage/{pruefung_id}", response_class=HTMLResponse)
def onpage_ergebnis(request: Request, pruefung_id: int, conn: Conn = Depends(sitzung)):
    try:
        r = onpage.holen(conn, pruefung_id)
    except onpage.OnpageFehler as e:
        raise HTTPException(404, str(e))
    projekt = _projekt(conn, r["projekt_id"])
    return _seite(request, "onpage.html", projekt=projekt, seiten=[], liste=onpage.liste(conn, projekt.id),
                  url=r["url"], keyword=r["keyword"], r=r)
