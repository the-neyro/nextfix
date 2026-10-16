# Site Audit: Berichtsaufbau und Einstellungen (Vorbild Semrush)

Quellen (öffentliches Hilfe-Center, abgerufen 2026-10-14):
- Overview: https://www.semrush.com/kb/540-site-audit-overview
- Health Score: https://www.semrush.com/kb/114-total-score
- Thematic Reports: https://www.semrush.com/kb/959-site-audit-thematic-reports
- Konfiguration: https://www.semrush.com/kb/539-configuring-site-audit
- Statistics / Compare / Progress: https://www.semrush.com/kb/544-site-audit-statistics, https://www.semrush.com/kb/545-site-audit-compare-crawls-progress

Eigene Zusammenfassung, keine Texte oder Grafiken übernommen.

## 1. Tabs (Ansichten)

| Tab | Inhalt | MVP |
|---|---|---|
| Overview | Kacheln + Vorschau der Thematic Reports | ✅ |
| Issues | alle Checks mit Treffern, nach Error/Warning/Notice, Filter nach Kategorie, „Warum + wie beheben“ pro Check | ✅ |
| Crawled Pages | Tabelle aller Seiten mit Kennzahlen; Ziel aller Klicks aus Diagrammen (gefiltert) | ✅ |
| Statistics | Diagramme: HTTP-Statuscodes, Sitemap vs. gecrawlt, Crawl-Tiefe, Canonicalization | ✅ |
| Compare Crawls | zwei Crawls nebeneinander, Spalten „behoben“ / „neu“ pro Check | ⏳ |
| Progress | Liniendiagramm über Zeit, Metriken wählbar (Allgemein, Errors, Warnings, Notices) | ⏳ |
| JS Impact | Unterschied mit/ohne JS-Rendering (Details nicht öffentlich) | ❌ |

## 2. Overview-Kacheln

- **Site Health** (0–100 %), mit Vergleich zum letzten Crawl.
- **Seiten-Aufteilung:** gesund / defekt / mit Problemen / Weiterleitung / blockiert.
- **Errors** und **Warnings**: Anzahl, Veränderung.
- **AI Search Health** + **Blocked from AI Search** (robots.txt sperrt KI-Bots wie OAI-SearchBot, PerplexityBot). ⏳
- **Top Issues:** nach Priorität und Anzahl betroffener Seiten, Klick → Details.
- **Thematic-Report-Vorschauen** (siehe 3).

## 3. Thematic Reports (Kategorien)

| Report | Zeigt | MVP |
|---|---|---|
| Robots.txt | Änderungen seit letztem Crawl, Probleme | ✅ |
| Crawlability | Crawl-Tiefe (Ziel < 3 Klicks), Statuscodes, Sitemap vs. gecrawlt | ✅ |
| HTTPS | 3 Blöcke: Zertifikat, Server-Support, Architektur (Mixed Content usw.) | ✅ |
| Internal Linking | Crawl-Tiefe, ein-/ausgehende Links, Orphans, Link-Verteilung, Top-Seiten nach interner Link-Stärke (eigener PageRank) | ✅ |
| Performance | Ø HTML-Ladezeit + Verteilung (0–0,5 / 0,5–1 / 1–3 / > 3 s), Trend, Anzahl/Größe JS+CSS pro Seite | ✅ |
| International SEO | Kreis: ohne hreflang / korrekt / fehlerhaft, Issues, Tabelle fehlender hreflang | ⏳ |
| Markups | Note aus gültig/ungültig, Seiten mit Markup, Typen, Items | ⏳ |
| Core Web Vitals | Lighthouse (LCP, CLS, TBT) für 10 Seiten, Verlauf | ⏳ (lokal mit Lighthouse machbar) |

Jeder Report hat einen eigenen Score; jede Zahl/Diagrammsegment ist klickbar → gefilterte Crawled Pages.

## 4. Health Score

Öffentlich ist **keine Formel**, nur Regeln:
- Basis: Errors und Warnings im Verhältnis zur Zahl der durchgeführten Checks.
- Errors wiegen mehr als Warnings, Notices kaum oder gar nicht.
- Einen Check **komplett** beheben bringt mehr als verstreute Einzelfixes.
- Nicht abhängig von der Anzahl gecrawlter Seiten.
- Ausgeschlossene Checks zählen nicht.

**Eigener Vorschlag (erfüllt diese Regeln):**

```
Gewicht w: Error = 3, Warning = 1, Notice = 0
Für jeden durchgeführten Check c:
  anteil_c = betroffene Seiten / geprüfte Seiten
  strafe_c = 0                          wenn keine Treffer
           = w_c * (0,5 + 0,5 * anteil_c) sonst
Health = 100 * (1 - Σ strafe_c / Σ w_c)
```

- Fester Sockel 0,5 → ein Check bleibt „teuer“, bis er ganz weg ist.
- Anteil statt Anzahl → unabhängig von der Seitenzahl.
- Thematic-Score = gleiche Formel, nur über die Checks der Kategorie.
- Gewichte in einer Config-Datei, damit wir sie später justieren können.

## 5. Einstellungen (Crawl-Konfiguration)

| Einstellung | Optionen (Semrush) | Default | MVP |
|---|---|---|---|
| Scope | Domain (inkl. Subdomains, abschaltbar), Subdomain, Unterordner | Domain + Subdomains | ✅ |
| Seitenlimit | Zahl pro Audit (bei Semrush tarifabhängig) | – | ✅ (frei, z. B. 500) |
| Crawl-Quelle | Website (Breitensuche ab Startseite), Sitemap aus robots.txt, Sitemap-URL, URL-Liste (.txt/.csv, 1 URL/Zeile) | Website | ✅ |
| User-Agent | Desktop-Bot, Mobile-Bot, OpenAI-Search | Mobile | ✅ (eigener UA-String) |
| Crawl-Delay | Minimum (~1 s), 1 URL/2 s, robots.txt beachten (max. 30 s) | Minimum | ✅ |
| JS-Rendering | an/aus | aus | ⏳ (Playwright) |
| Allow/Disallow | Unterordner-Pfade (mit Slash am Ende) | – | ✅ |
| URL-Parameter ignorieren | Parameternamen | – | ✅ |
| Einschränkungen umgehen | robots.txt ignorieren (bei Semrush nur mit Eigentumsnachweis), Login-Daten, Web-Bot-Auth | – | ⏳ (lokal: Schalter „robots.txt ignorieren“ nur für eigene Sites) |
| Zeitplan | einmalig, täglich, wöchentlich (Wochentag) | – | ⏳ |

## 6. Sonstiges

- **Export:** PDF, XLSX, CSV. MVP: CSV + HTML/PDF-Bericht.
- **Re-Run** jederzeit; laufenden Crawl stoppen (speichern oder verwerfen).
- **Checks ausschließen** pro Projekt (fließen dann nicht in den Score).
- **Historie:** Crawls speichern → Grundlage für Compare/Progress.

## Fazit für das Datenmodell

Projekt (Einstellungen) → Crawl (Zeitpunkt, Scores) → Seite (URL, Status, Tiefe, Ladezeit, Größe, Links rein/raus, interne Link-Stärke) → Issue (Check-ID, Seite, Detail). Checks als Katalog mit ID, Schweregrad, Kategorie, Text „Warum/wie beheben“.
