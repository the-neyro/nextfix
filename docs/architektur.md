# Architektur

Stand: 2026-10-14

## Grundprinzip: ein Kern, drei Zugänge

Jede Funktion steckt genau einmal im **Kern** (Python-Services). Darauf sitzen gleichwertige Zugänge:

```
                ┌── Web-UI (FastAPI + Jinja + HTMX)   → Mensch im Browser
Kern (Services) ├── REST-API (FastAPI, /api/...)      → Skripte, später andere Tools
                └── MCP-Server                        → Claude als Assistent
```

Regel: **Keine Funktion nur in der UI.** Was ein Mensch in der UI kann, kann Claude über MCP auch:
Projekt anlegen, Einstellungen ändern, Crawl starten/stoppen, Status abfragen, Issues filtern,
Seiten ansehen, Crawls vergleichen, Checks ausschließen, Export erzeugen.

So arbeiten Nutzer und Claude auf denselben Daten: Nutzer sieht im Browser, was Claude gestartet hat, und umgekehrt.

## Stack

| Teil | Wahl |
|---|---|
| Kern + API + UI | Python 3.14, FastAPI |
| Crawler | httpx (async) + selectolax |
| Datenbank | SQLite (eine Datei, lokal) |
| Frontend | Jinja-Templates + HTMX + Chart.js, ohne Build |
| Assistent-Zugang | MCP-Server (Python `mcp`-SDK), nutzt dieselben Services |
| Tests | pytest + lokale Testseite |
| Später | Playwright (JS-Rendering), Lighthouse via Node (Core Web Vitals), evtl. Tauri als Desktop-Hülle |

## Module (geplant)

```
app/
  core/        Services: projekte, crawls, issues, scores, export
  crawler/     Abruf, robots.txt, Sitemap, Link-Queue
  checks/      ein Modul pro Check + Katalog (ID, Schweregrad, Kategorie, Texte)
  db/          SQLite-Schema und Zugriff
  web/         FastAPI-Routen + Templates (UI)
  api/         REST-Routen
  mcp_server/  MCP-Tools, 1:1 auf Services
tests/
```

## Offene Frage

- Zusätzlich Chat **in der App** (Claude-API, kostet pro Nutzung, braucht API-Key) oder reicht Claude Code über MCP?
