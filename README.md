# Nextfix

**SEO-Tool, das sagt, was als Nächstes zu tun ist.** Läuft lokal, kostet nichts, und Claude kann es über MCP
komplett bedienen.

Große SEO-Suiten zeigen Hunderte Zahlen – Errors, Warnings, Notices – und lassen offen, womit man anfangen soll.
Nextfix prüft eine Website ähnlich gründlich und macht daraus eine kurze Liste: **was zuerst, warum, wie, und
wie viel es bringt.**

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/uebersicht-dunkel.png">
  <img alt="Projekt-Übersicht: Website-Zustand als Messskala, Teilnoten und die Liste „Was jetzt tun“" src="docs/screenshots/uebersicht-hell.png">
</picture>

<sub>Alle Screenshots zeigen die erfundene Demo-Website „Radhaus Elbe“ (`scripts/demo_website.py`).</sub>

## Was es kann

| Modul | Frage, die es beantwortet |
|---|---|
| **Website-Check** | Was ist kaputt, und was zuerst? Crawler (Links, Sitemap oder beides, robots.txt), 101 Prüfungen in 8 Bereichen, Website-Zustand 0–100, Aufgaben nach gewinnbaren Punkten, „Bewusst so“ zum Ausblenden absichtlicher Fälle, Verlauf zwischen Prüfungen, CSV und PDF-Bericht. |
| **Ladezeit** | Ist die Seite schnell genug? Core Web Vitals (LCP, CLS, TBT) im Labor mit echtem Chromium, mobil und Desktop, Score nach Lighthouse-Formel – gegen PageSpeed Insights abgeglichen. |
| **Positionen** | Wo werde ich gefunden, wo verliere ich? Daten aus Google Search Console und Bing Webmaster Tools: Sichtbarkeit, Aufsteiger und Absteiger, „fast auf Seite 1“, mehrere Seiten für einen Suchbegriff, täglicher Import. |
| **Suchbegriffe finden** | Worüber lohnt es sich zu schreiben? Ideen aus Google-Vorschlägen und eigenen Search-Console-Daten, Gruppen, Suchabsicht, Fragen, Suchvolumen über Bing, Themen-Lücke zu Mitbewerbern. |
| **Seite optimieren** | Was ändere ich an dieser Seite? Seiten-Score für einen Suchbegriff (20 Regeln) plus KI-Score (12 Regeln für ChatGPT, Perplexity & Co.), „Zuerst diese 3“ mit konkretem Vorschlag zum Kopieren. |

Dazu Prüfungen für die **KI-Suche (GEO)**: llms.txt, gesperrte KI-Crawler, Belege, FAQ-Markup, Autor und Datum,
Organisations-Markup – angelehnt an die GEO-Studie (Princeton, KDD 2024).

| | |
|---|---|
| ![Problem im Detail: warum, wie beheben, Fundstellen nach Bereich](docs/screenshots/problem-hell.png) | ![Seite optimieren: Zuerst diese 3 mit Vorschlag](docs/screenshots/seite-optimieren-hell.png) |
| **Ein Problem im Detail** – warum es zählt, wie man es behebt, Fundstellen gruppiert nach Vorlage | **Seite optimieren** – Seiten- und KI-Score, die drei wirksamsten Änderungen mit Vorschlag |
| ![Positionen mit Testdaten](docs/screenshots/positionen-dunkel.png) | ![Projektliste](docs/screenshots/projekte-dunkel.png) |
| **Positionen** – Kennzahlen und Chancen „fast auf Seite 1“ (hier Testdaten) | **Projekte** – alle Websites mit ihrem Zustand |

## Was anders ist

- **Aufgaben statt Zahlenwand.** Jedes Problem bekommt einen Satz mit Handlung, Aufwand („einmal einstellen“,
  „Text schreiben“), wer es macht (selbst im CMS oder Technik) und die Punkte, die der Website-Zustand gewinnt.
- **Ehrlicher Zustand.** Die Formel verdünnt Probleme nicht über Prüfungen, die nie anschlagen; dünner Inhalt auf
  vielen Seiten wiegt wie ein Fehler (`app/core/score.py`).
- **Klartext.** Dringend / Wichtig / Feinschliff statt Error / Warning / Notice, Fachbegriffe mit Erklärung.
- **Null Kosten.** Keine bezahlten APIs, keine Google-Suchergebnisse abgefragt (Nutzungsbedingungen). Rankings
  kommen nur aus Search Console und Bing – den Quellen, die dem Website-Besitzer ohnehin gehören.
- **Drei Zugänge, ein Kern.** Web-UI, REST-API (`/docs`) und MCP-Server für Claude nutzen dieselben Funktionen.
- **Hell und dunkel**, auf dem Handy bedienbar, läuft offline (Schrift und HTMX liegen im Projekt).

## Schnellstart

Voraussetzung: Python 3.12 oder neuer.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium          # für Ladezeit und PDF-Bericht
.venv/bin/uvicorn app.web:app --reload         # http://localhost:8000
```

Dann eine Domain anlegen und „Website prüfen“ klicken. Ohne eigene Website zum Ausprobieren:

```bash
.venv/bin/python -m scripts.demo_website 8798  # Demo-Website „Radhaus Elbe“ auf http://127.0.0.1:8798/
```

Im Tool ein Projekt mit Start-Adresse `http://127.0.0.1:8798/` anlegen. Positionen lassen sich ohne Zugang mit
Testdaten ausprobieren.

### Mit Claude (MCP)

```bash
.venv/bin/python -m app.mcp_server             # MCP-Server (stdio)
```

Für Claude Code `.mcp.json.example` nach `.mcp.json` kopieren und den Projektpfad eintragen. 49 Tools, z. B. `crawl_starten`, `issues_liste`, `onpage_pruefen`,
`positionen_uebersicht`, `keyword_recherche_starten`, `vitals_messen`, `pdf_bericht`.

### Google Search Console und Bing

Anleitungen: [`docs/anleitung-gsc.md`](docs/anleitung-gsc.md), [`docs/anleitung-bing.md`](docs/anleitung-bing.md).
Schlüssel liegen außerhalb des Projekts unter `~/.config/seo-tool/` und gelangen nie ins Git.

## Entwicklung

```bash
.venv/bin/python -m pytest -q                  # Tests (ohne Netz)
.venv/bin/python -m scripts.screenshots        # Screenshots neu erzeugen (eigene Demo-Datenbank)
```

| Ordner | Inhalt |
|---|---|
| `app/core/` | Services, die ganze Logik |
| `app/checks/` | Prüf-Katalog: ein `@check` pro Prüfung, ein Modul je Bereich |
| `app/crawler/` | Crawler, Parser, Labor-Messung der Ladezeit |
| `app/onpage/` | Seiten-Check gegen einen Suchbegriff, KI-Score |
| `app/gsc/`, `app/keywords/` | Search Console, Bing, Google-Vorschläge |
| `app/web/` | Web-UI (Jinja + HTMX), Design-System in `static/app.css` |
| `app/api/`, `app/mcp_server/` | REST-API und MCP-Tools |
| `app/berichte/` | PDF-Bericht (Playwright) |
| `scripts/` | Demo-Website und Screenshot-Skript |
| `docs/` | Architektur, Anleitungen, UI-Konzept (`docs/ui/`) |

Regel: Neue Funktion zuerst in `app/core/`, dann in API, UI **und** MCP anbinden, plus Test.
Daten liegen in `data/seo.db` (SQLite, nicht im Git); anderer Pfad über `SEO_DB`.

## Grenzen

- Keine Backlink-Daten und keine Positionen von Mitbewerbern – dafür bräuchte es bezahlte Datenbanken.
- Der Crawler führt kein JavaScript aus; Inhalte, die nur per JS entstehen, sieht er nicht.
- Ladezeit ist eine Labor-Messung, keine Felddaten echter Nutzer (CrUX).

## Lizenz

[MIT](LICENSE). Schrift: [Fira Sans](https://github.com/mozilla/Fira) (SIL Open Font License, `app/web/static/fonts/OFL.txt`).
HTMX 2.0.4 (BSD-2-Clause).
