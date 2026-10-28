# Design-System „Akzent-Leiter“

Eine Gestaltung für App, PDF-Bericht und Website. Quelle der Werte: `app/web/static/app.css` (Tokens ganz oben).

## Idee
- Die Markenfarbe **Himbeere `#b8336a`** steht nur auf kleinen Marken: der eine gefüllte Knopf, Datenbalken, der aktive Navigationspunkt (Punkt).
- Flächen tragen die hellen Tints: `--akzent-flaeche` (Karten, Lead-Aufgabe), `--akzent-spur` (Spuren, aktive Navigationszeile), `--akzent-tinte` (Schrift darauf).
- Signalfarben nur für Status, immer mit Form und Wort: ◆ dringend, ▲ wichtig, ● Feinschliff, ✓ gut. Keine Farbe pro Teilnote.
- Kein Violett, kein Verlauf, kein Schatten im Ruhezustand (Schatten nur bei Menüs).

## Tokens (hell / dunkel)
| Token | hell | dunkel |
| --- | --- | --- |
| `--grund` | `#fbf7f8` | `#0e0e0f` |
| `--flaeche` | `#ffffff` | `#161617` |
| `--text` / `--gedaempft` | `#111827` / `#5f6672` | `#f4f4f5` / `#b4b4b8` |
| `--linie` | `#ebe5e8` | `#2a2a2d` |
| `--akzent` | `#b8336a` | `#e2759f` |
| `--akzent-flaeche` / `--akzent-spur` | `#fdf2f7` / `#f8dbe8` | `#2a1520` / `#43202f` |
| `--kritisch` / `--wichtig` / `--gut` | `#c4242a` / `#92400e` / `#247b50` | `#ff8f8a` / `#f0b25a` / `#52c78c` |

Dunkel ist neutrales Schwarzgrau mit derselben Leiter, kein Blau.

## Schrift
**DM Sans**, lokal (`static/fonts/`, variabel, SIL OFL 1.1, `OFL-DM-Sans.txt`). Gewichte 400 bis 700; 700 nur für den Seitentitel. Größen: Titel 32 · Abschnitt 18 · Kennzahl 24 · Text 14 · klein 13. Tabellenzahlen tabellarisch. Monospace nur für Code und Pfade.

## Rahmen
Seitenleiste 232 px und Kopfleiste 64 px teilen einen Grund, getrennt nur durch 1-px-Linien. Kopfleiste: Domain links, Projektwahl rechts hinter einer Trennlinie. Auf dem Handy: 56 px, Menü-Knopf, Navigation klappt unter der Leiste auf.

## Übersicht
Lead-Block ist „Was jetzt tun“: die erste Aufgabe groß auf Tint-Fläche mit dem einzigen gefüllten Knopf, der Rest als Liste. Rechts eine Spalte (384 px): Website-Zustand als ruhige Zahl mit Spur (Striche bei 50 und 80), Teilnoten, Geprüfte Seiten.

## App-Icon
Entwürfe in `static/icon-varianten/` (Vorschau: `vorschau.html`). `static/logo.svg` ist eine Kopie der gewählten Variante; Austausch ist eine Datei.
