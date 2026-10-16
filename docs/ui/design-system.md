# Design-System „Prüfstand“

Stand: 16.10.2026 · Plan, noch nicht umgesetzt. Grundlage: `base.html`, `_uebersicht.html`, `issues.html`, `positionen.html`, `_onpage_ergebnis.html`, `vitals.html`.

## 1. Konzept

Das Tool macht mit einer Website, was ein Prüfer mit einem Auto macht: messen, Mängel protokollieren, Grenzwerte zeigen, Plakette vergeben. Die Oberfläche sieht aus wie ein **ruhiges Messinstrument mit Prüfprotokoll**: Zahlen stehen auf Skalen mit sichtbaren Grenzwerten (nicht nur „73 %“, sondern *wo* die 80 liegt), Befunde lesen sich wie Protokollzeilen mit klarer Handlung. Der Akzent ist **Stempelviolett**, die Farbe der Prüfstempel, und gehört nur zu Aktionen und Auswahl, nie zu einem Status.

## 2. Farben

Alle Werte mit Skript gerechnet (WCAG 2.1, Relativ-Luminanz). AA = 4,5:1 für Text, 3:1 für Bedienelemente/Icons.

| Token | Hell | Dunkel | Kontrast hell / dunkel |
|---|---|---|---|
| `--grund` (Seite, Seitenleiste) | `#EEF0F2` | `#14171D` | – |
| `--flaeche` (Panels, Tabellen) | `#FFFFFF` | `#1C2028` | – |
| `--flaeche-2` (Tabellenkopf, Hover) | `#F6F7F9` | `#242934` | – |
| `--text` | `#1B1F2A` | `#E4E7EE` | 16,5 / 13,2 auf Fläche |
| `--gedaempft` (Hilfstext, Achsen) | `#596070` | `#9BA2B1` | 6,3 / 6,4 (auf Grund 5,5 / 7,0) |
| `--linie` (Trenner, nur deko) | `#DCDFE4` | `#323845` | 1,3 / 1,4 – bewusst schwach |
| `--linie-stark` (Eingabefeld-Rand) | `#868D9A` | `#6E7687` | 3,3 / 3,6 ✓ 3:1 |
| `--akzent` (Stempelviolett) | `#5B3FBF` | `#A897FF` | 7,2 / 6,6 |
| `--akzent-flaeche` (Auswahl, aktiver Nav-Punkt) | `#EEEAFA` | `#2A2546` | Akzent darauf 6,1 / 5,9 |
| `--auf-akzent` (Text auf Button) | `#FFFFFF` | `#14171D` | 7,2 / 7,3 |
| `--kritisch` (bisher error) | `#C0261A` | `#FF7D6E` | 5,9 / 6,5 |
| `--wichtig` (bisher warning) | `#985400` | `#EFB04A` | 5,8 / 8,5 |
| `--hinweis` (bisher notice) | `#2D6688` | `#7FB5DA` | 6,2 / 7,4 |
| `--gut` | `#1D7544` | `#5FCB8D` | 5,7 / 8,1 |
| `--kritisch-flaeche` / `--wichtig-` / `--hinweis-` / `--gut-` | `#FBEAE8` `#FBF0DF` `#E6F0F6` `#E5F3EA` | `#3A2224` `#382D1C` `#1E2E3A` `#1C3127` | Statusfarbe darauf 5,1 / 5,2 / 5,4 / 5,0 bzw. 5,9 / 7,0 / 6,3 / 6,9 |

Regeln: Hinweis ist ein ruhiges Schieferblau, damit es nicht mit dem Violett der Aktionen verwechselt wird. Diagrammlinien: Hauptreihe `--akzent`, Vergleich `--gedaempft` gestrichelt. Kein Verlauf, keine Glow-Effekte.

**Umschalter:** drei Zustände *System · Hell · Dunkel* als kleines Segment unten in der Seitenleiste. `data-theme` auf `<html>`, Wahl in `localStorage` (try/catch), Mini-Skript im `<head>` vor dem CSS gegen Aufblitzen.

```css
:root {
  --grund:#EEF0F2; --flaeche:#FFFFFF; --flaeche-2:#F6F7F9; --text:#1B1F2A; --gedaempft:#596070;
  --linie:#DCDFE4; --linie-stark:#868D9A; --akzent:#5B3FBF; --akzent-flaeche:#EEEAFA; --auf-akzent:#FFFFFF;
  --kritisch:#C0261A; --wichtig:#985400; --hinweis:#2D6688; --gut:#1D7544;
  --kritisch-flaeche:#FBEAE8; --wichtig-flaeche:#FBF0DF; --hinweis-flaeche:#E6F0F6; --gut-flaeche:#E5F3EA;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { /* = Block unten */ } }
:root[data-theme="dark"] {
  --grund:#14171D; --flaeche:#1C2028; --flaeche-2:#242934; --text:#E4E7EE; --gedaempft:#9BA2B1;
  --linie:#323845; --linie-stark:#6E7687; --akzent:#A897FF; --akzent-flaeche:#2A2546; --auf-akzent:#14171D;
  --kritisch:#FF7D6E; --wichtig:#EFB04A; --hinweis:#7FB5DA; --gut:#5FCB8D;
  --kritisch-flaeche:#3A2224; --wichtig-flaeche:#382D1C; --hinweis-flaeche:#1E2E3A; --gut-flaeche:#1C3127;
  color-scheme: dark;
}
```

## 3. Schrift

**Fira Sans** + **Fira Sans Condensed** (eine Familie, zwei Breiten), SIL OFL 1.1.
- Von Erik Spiekermann (Berlin) aus der FF-Meta-Tradition: gebaut für Lesbarkeit auf Bildschirmen und in kleinen Größen, deutsche Typografie-Schule, saubere Umlaute und ß, ẞ im latin-ext-Teil.
- Tabellarische Ziffern über `font-variant-numeric: tabular-nums` (Feature `tnum`) – nach Einbau mit einer Testzeile „111 / 888“ prüfen.
- Condensed für dichte Tabellen (URL-Spalte, Kennzahlen-Spalten) und Skalen-Beschriftung: mehr Inhalt pro Zeile ohne Monospace-Look.

**Quelle (fontsource über jsDelivr, einmal herunterladen, dann unter `app/web/static/fonts/` ausliefern):**
`https://cdn.jsdelivr.net/npm/@fontsource/fira-sans@5.2.7/files/fira-sans-{subset}-{gewicht}-{stil}.woff2`
`https://cdn.jsdelivr.net/npm/@fontsource/fira-sans-condensed@5.2.7/files/fira-sans-condensed-{subset}-{gewicht}-normal.woff2`
- subset: `latin` (ä ö ü ß, ~24 KB je Datei) + `latin-ext` mit `unicode-range` (nur bei Bedarf geladen). URLs am 16.10. getestet (HTTP 200).
- Benötigt: Fira Sans 400, 400-italic, 500, 600 · Condensed 400, 500. Zusammen ~150 KB. `font-display: swap`. Lizenzdatei `OFL.txt` mit ins Repo.

**Skala** (Basis 14 px für die App, Verhältnis ~1,2):

| Rolle | Größe / Zeile | Gewicht | Einsatz |
|---|---|---|---|
| Messwert groß | 44 / 48 | 500, tnum | nur Health auf der Übersicht |
| Seitentitel | 24 / 30 | 600 | Projektname |
| Abschnitt | 18 / 24 | 600 | „Was jetzt tun“, „Je Seite“ |
| Kennzahl | 28 / 32 | 500, tnum | Kennzahlen-Leiste |
| Fließtext | 14 / 21 | 400 | Erklärungen, max. 72 Zeichen Breite |
| Tabelle | 13 / 18 | 400, tnum | Condensed in URL- und Zahlen-Spalten |
| Klein / Label | 12,5 / 16 | 500 | Feld-Labels, Achsen, Tabellenkopf – Satzschreibung, keine Versalien |

## 4. Layout

```
┌────────────┬──────────────────────────────────────────────┐
│ Projekt ▾  │ beispiel.de        Crawl vom 15.10., 214 Seiten │
│            │──────────────────────────────────────────────│
│ Website    │ [ Messskala Health ═════════|══▲═══ 73 ]     │
│  Übersicht │ Kennzahlen-Leiste │ │ │ │                     │
│  Befunde 42│──────────────────────────────────────────────│
│  Seiten    │ Was jetzt tun (8 Spalten) │ Bereiche (4 Sp.) │
│  Ladezeit  │                           │                  │
│ Sichtbark. │                                              │
│ Inhalt     │                                              │
│ ◐ System   │                                              │
└────────────┴──────────────────────────────────────────────┘
```
- **Seitenleiste** 232 px, gleiche Farbe wie `--grund` (kein dunkler Navy-Balken), Gruppen „Website prüfen“, „Sichtbarkeit“, „Inhalt“; Gruppentitel 12,5 px gedämpft. Aktiver Punkt: `--akzent-flaeche` + Text `--akzent`. Unter 900 px wird sie zur Kopfleiste mit Menü-Button.
- **Inhalt** linksbündig, max. 1240 px, 12-Spalten-Raster, Spaltenabstand 24 px, Seitenrand 32 px (mobil 16 px).
- **Abstände** (4er-Basis): 4 · 8 · 12 · 16 · 24 · 32 · 48. Innerhalb von Komponenten 8–16, zwischen Abschnitten 32–48.
- **Radien mit Hierarchie:** Panel 8 px · Button/Feld 6 px · Status-Marke 3 px (gestempeltes Etikett, keine Pille) · Messskala 0 px (Instrument).
- **Schatten:** nein. Trennung über Fläche gegen Grund + 1 px `--linie`. Einzige Ausnahme: Popover/Dialog `0 8px 24px rgb(20 23 29 / .18)`. Dunkel: höhere Ebene = hellere Fläche.

## 5. Komponenten

- **Kennzahl:** keine Einzelkarten. Eine Kennzahlen-Leiste = ein Panel, durch senkrechte Linien geteilt. Je Zelle: Label (12,5, gedämpft) · Wert (28, tnum) · Veränderung als Pfeil + Vorzeichen + Wort („▲ 3 besser“), Farbe gut/kritisch nur zusätzlich. Ø Position: kleiner = besser, Text sagt das.
- **Tabelle:** Zeilenhöhe 36 px (dicht: 30 px), Kopf `--flaeche-2`, klebt beim Scrollen, Satzschreibung. Zahlen rechtsbündig, tnum, Einheit gedämpft („2,4 s“). URLs in Condensed, mittig gekürzt (`/ratgeber/…/seo-check`), voller Wert im `title`. Kein Zebra; Hover-Zeile `--flaeche-2`. Ganze Zeile klickbar, wenn es eine Detailseite gibt. Breite Tabellen scrollen in ihrem Container, nie die Seite.
- **Status-Marke (nie nur Farbe):** Form + Wort + Farbe. Kritisch ◆ · Wichtig ▲ · Hinweis ● · Gut ✓. Marke: getönte Statusfläche, 3 px Radius, Symbol in Statusfarbe, Wort in `--text`. Deutsche Wörter statt „error/warning/notice“. In Tabellen reicht Symbol + `aria-label`.
- **Health/Fortschritt:** Messskala (siehe 6). Kleinform für Bereiche: 6 px hohe Leiste ohne Rundung, Füllung in Statusfarbe der Stufe, Grenzstriche bei 50 und 80 als 1-px-Ticks über der Leiste, Wert rechts daneben.
- **Buttons:** Primär = `--akzent` gefüllt, `--auf-akzent`, 36 px hoch, 600. Sekundär = `--flaeche` mit 1 px `--linie-stark`, Text `--text`. Leise = nur Text in `--akzent`. Gefährlich (Löschen) = sekundär mit Text `--kritisch`, immer mit Bestätigung. Pro Bereich höchstens ein primärer Button. Beschriftung = Verb + Objekt („Crawl starten“, „Testdaten löschen“), kein Pfeil.
- **Formulare:** Label über dem Feld, Hilfetext darunter (gedämpft), Felder 36 px, Rand `--linie-stark`, Fokus: Rand `--akzent` + 3 px Ring `--akzent-flaeche`. Fehler: Rand `--kritisch` + Zeile „◆ Domain fehlt – z. B. beispiel.de“. Filterleisten als eine Zeile über der Tabelle, nicht in eigener Karte.
- **Tabs:** nur für Ansichten *innerhalb* einer Seite (Google/Bing, Mobil/Desktop). Text gedämpft, aktiv `--text` + 2 px Unterstrich `--akzent`, Zähler als kleine graue Zahl. Hauptnavigation wandert in die Seitenleiste.
- **Aufgaben-Zeile („Was jetzt tun“):** echte Reihenfolge nach Wirkung, daher nummeriert. Aufbau: Nr. (tnum, gedämpft) · Status-Symbol · Handlung als Satz („Fehlende Seitentitel ergänzen“) · darunter ein Satz *warum* · rechts „17 Seiten“ und Button „Seiten ansehen“. Aufklappbar für die Trefferliste (vorhandenes HTMX-`details`). Erledigt = durchgestrichen nur bis zum nächsten Crawl, dann prüft der Crawl selbst.
- **Leere Zustände:** ein Satz, was fehlt, ein Satz, was passiert, ein Button. Beispiel: „Noch kein Crawl für beispiel.de. Der erste Durchlauf dauert bei 200 Seiten etwa 3 Minuten. [Crawl starten]“. Gute Leere („Keine kritischen Befunde“) mit ✓ in `--gut`, ruhig, ohne Konfetti. Fehler sagen Ursache + Lösung, keine Entschuldigung.
- **Diagramme:** Linie 2 px, Achsen und Raster in `--linie`, Beschriftung 12,5 gedämpft. Position-Achse umgekehrt mit Hinweis „oben = besser“ direkt an der Achse.

## 6. Das eine einprägsame Element: die Messskala

Health-Score der Übersicht als breites, liegendes Messband über die volle Inhaltsbreite statt Prozent-Karte oder Donut: Millimeter-Ticks (alle 5 kurz, alle 10 lang, Zahlen bei 0/50/80/100 in Condensed), Zonen unter dem Band als dünne Streifen in Kritisch/Wichtig/Gut-Fläche, darüber ein Zeiger ▼ mit dem Wert in 44 px. Links daneben ein Satz: „73 von 100 – 7 Punkte bis ‚gut‘“. Der Vorwert des letzten Crawls bleibt als hohler Zeiger ▽ stehen, so sieht man den Fortschritt ohne Diagramm.
Dieselbe Skala gibt es klein für Core Web Vitals (LCP mit Zonen 2,5 s / 4 s) und für On-Page- und KI-Score. Das ist auch das Bild für die GitHub-Screenshots.
Einzige Bewegung im Tool: Beim ersten Laden fährt der Zeiger einmal vom Vorwert zum neuen Wert (400 ms, ease-out, aus bei `prefers-reduced-motion`).

**Bewusst ruhig:** Seitenleiste, Tabellen, Formulare, Buttons, Diagramme. Keine Icons in der Navigation außer Statussymbolen, keine Hover-Animationen, keine Illustrationen.

## 7. Selbstkritik: was Standard gewesen wäre

| Erster Reflex (generisch) | Überarbeitet | Warum |
|---|---|---|
| Inter oder IBM Plex | Fira Sans + Condensed | Inter ist der KI-Standard. Fira passt zur deutschen Info-Design-Tradition und bringt eine schmale Breite für Tabellen mit. |
| Akzent Blau `#2563EB` | Stempelviolett `#5B3FBF` | Blau kollidiert mit „Hinweis“ und sieht nach jedem SaaS aus. Violett kommt aus dem Prüfstempel und ist von allen Statusfarben klar getrennt. |
| Fünf gleiche KPI-Karten mit 10 px Radius und grauem Schatten | Eine geteilte Kennzahlen-Leiste, Radien gestuft, keine Schatten | Genau das „SaaS-Karten-Kit“; die Kennzahlen gehören zusammen, also ein Container. |
| Health als Donut/Tacho | Liegende Messskala mit Grenzwerten und Vorwert | Ein Donut zeigt nur den Wert; die Skala zeigt zusätzlich, wo „gut“ anfängt und wie weit man gekommen ist. |
| Dunkle Navy-Seitenleiste | Seitenleiste im Grundton | Vermeidet den Standard-Admin-Look und lässt die Messskala das Auffälligste bleiben. |
| Pillen-Badges „error“ in Vollfarbe | Eckige Etiketten mit Form + deutschem Wort, getönt | Zugänglich ohne Farbe, verständlich für Nicht-SEOs, weniger laut auf langen Listen. |
| Dark Mode `#0B0B0B` + Neonakzent | Blaugrafit `#14171D` mit gedämpftem Violett | Kein Schwarz+Neon-Klischee, angenehm bei langen Tabellen. |
| Englische Tabs „Issues“, „Core Web Vitals“ | „Befunde“, „Ladezeit“ (Fachbegriff klein dahinter) | Der Nutzer ist kein SEO-Profi; Fachwort nur als Zusatz. |

Noch offen: Ob ◆/▲/● in Fira Sans selbst enthalten sind, beim Einbau prüfen; sonst als kleine Inline-SVGs.
