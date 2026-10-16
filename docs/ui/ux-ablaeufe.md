# UX: Informationsarchitektur und Abläufe

Stand 16.10.2026 · Grundlage: Templates in `app/web/templates/`, laufende UI (Beispielprojekt mit echten Daten).
Leitsatz: **Jede Seite beantwortet oben eine Frage und bietet genau eine nächste Aktion.**

## 0. Befund heute (konkret)
- Audit-Startseite beginnt mit Crawl-Einstellungen (101 Checkboxen im DOM) statt mit dem Ergebnis.
- Zwei Tab-Ebenen (Module + Audit-Unterseiten), Vitals hängt unter Audit, URLs wechseln zwischen `/projekte/3` und `/crawls/13` – der Nutzer verliert den Ort.
- Zahlen widersprechen sich: Health **96 %**, aber „129 von 187 Seiten mit Errors/Warnings“; „Performance 100 % · 182 Issues“, „KI-Suche 100 % · 167 Issues“ (Notices zählen als Issues, haben aber Gewicht 0).
- Errors/Warnings/Notices als nackte Zahlen (11 / 140 / 424) – sagt nicht, was zuerst.
- Kein Projektwechsel ohne Umweg über `/`; kein Weg Audit-Seite → On-Page-Prüfung.

## 1. Navigation
- **Seitenleiste links** (fest, ~200 px), oben **Projektwechsler** (Dropdown: Name + Domain + Health-Punkt, „+ Neues Projekt“).
- Module, je ein Eintrag, Klartext + Fachbegriff klein:
  `Übersicht` · `Technik-Check (Site Audit)` · `Ladezeit (Core Web Vitals)` · `Google-Positionen` · `Keyword-Ideen` · `Seite optimieren (On-Page)` · unten `Einstellungen`.
- Unterseiten nur innerhalb des Moduls als Tabs (Audit: Aufgaben · Alle Prüfungen · Seiten · Verlauf).
- URLs immer projektbezogen: `/projekte/3/audit`, Crawl-Auswahl als Dropdown „Stand vom 15.10.“ (Standard = neuester), nicht als ID im Pfad.
- Crawl-Einstellungen, GSC/Bing-Zugang, Auto-Import, ausgeschlossene Checks → **Einstellungen** des Projekts. Nicht über Ergebnissen.
- **Projekt-Startseite = Übersicht** („Cockpit“): Was jetzt tun + je Modul eine Kachel mit einer Zahl, Trend und nächster Aktion.

## 2. Module: Hauptaufgabe, oben, Details, Ablauf
| Modul | Die eine Frage | Oben | In Details |
|---|---|---|---|
| Übersicht | Was mache ich heute? | Top-5-Aufgaben aus allen Modulen, Fortschritt | Modul-Kacheln |
| Technik-Check | Was ist kaputt, was zuerst? | Aufgabenliste, Health mit Δ zum letzten Crawl | Kategorien, alle 101 Checks, Seitenliste, CSV/PDF |
| Ladezeit | Ist die Seite schnell genug? | Ampel mobil/Desktop: „6 von 10 Seiten bestehen“, langsamste Seite + Hauptursache | Messwerte je Seite (LCP/CLS/TBT…), Methodik-Text |
| Positionen | Werde ich gefunden, wo verliere ich? | Sichtbarkeit + Trend, „Chancen: 12 Begriffe fast auf Seite 1“, größte Verlierer | Begriffstabelle, Kannibalisierung, Tracking-Liste, Filter |
| Keyword-Ideen | Worüber soll ich schreiben? | Themen-Gruppen mit Intent („Ratgeber“, „Kaufen“), je Gruppe beste 3 Begriffe | Volle Liste, Volumen, Fragen, Themen-Lücke |
| On-Page | Was ändere ich an dieser Seite? | Score + Δ, **Top-3-Änderungen mit Vorher/Vorschlag** | Alle 20+12 Prüfungen, Begriffe, FAQ, Mitbewerber |

Typische Abläufe (jede Ergebnisseite verlinkt den nächsten Schritt):
- **Audit:** Prüfen → Aufgabenliste → Aufgabe öffnen → betroffene Seite ansehen (Befund + Vorschlag) → beheben → „Erneut prüfen“ → Aufgabe wird grün „erledigt“.
- **Positionen:** Chance „fast Seite 1“ anklicken → „Diese Seite optimieren“ (On-Page vorbefüllt mit URL + Begriff).
- **Keywords:** Gruppe wählen → „Zu Tracking hinzufügen“ oder „Passende Seite optimieren“ (On-Page vorbefüllt).
- **On-Page:** URL + Keyword (beides vorgeschlagen: Seiten aus Crawl, Keyword aus Title/GSC) → Top-3 umsetzen → „Neu prüfen“ → Δ-Score.
- **Ladezeit:** läuft nach Crawl automatisch (10 Seiten), Ergebnis landet als Aufgabe in der Übersicht.

## 3. „Was jetzt tun“ statt Error/Warning/Notice
- **Aufgabe = ein fehlgeschlagener Check**, formuliert als Handlung: „Kürze 22 Titles auf ≤ 70 Zeichen“, nicht „Title zu lang (> 70 Zeichen)“.
- **Priorität = gewinnbare Health-Punkte** (gleiche Formel wie `app/core/score.py`). So passt die Reihenfolge immer zur Health-Zahl.
  **Angezeigt wird nur die Wirkung hoch / mittel / gering** (Stand 16.10.2026), keine Punktzahl: „+4,2 Punkte“ täuschte eine Genauigkeit vor, die unsere eigene Formel nicht hat, und klang nach Ranking-Gewinn.
  Feinsortierung: × 1,5 wenn Startseite oder Seiten mit hoher Link-Stärke betroffen; bei Gleichstand zuerst geringer Aufwand.
- **Aufwand** pro Check im Katalog ergänzen: `leicht` (Text ändern), `mittel` (Template/Plugin), `technisch` (Server/Entwickler). Als Etikett zeigen.
- **Ursache bündeln:** gleiche Abweichung auf vielen Seiten mit gleichem Pfadmuster → „vermutlich 1 Template: /glossar/*“.
- **Anzahl:** 5 sichtbar, „weitere 9 anzeigen“. Notices (Gewicht 0) nie in der Liste, sondern unten eingeklappt „Feinschliff (11)“; nicht als „Issues“ in Kategorien zählen.
- **Fortschritt nach neuem Crawl** (Vergleich mit Vorgänger-Crawl, Daten aus `crawl_vergleich`):
  `✓ erledigt` (grün, durchgestrichen, 1 Crawl lang sichtbar) · `↓ besser 22→6` · `= unverändert` · `NEU` · `↑ schlimmer`.
  Kopfzeile: „Seit 01.10.: 4 von 9 Aufgaben erledigt · Health 88 → 96“.
- **„Bewusst so“** pro Aufgabe oder pro Seite (z. B. noindex auf Impressum): fliegt aus Liste und Health, Zähler „2 ausgeblendet“ bleibt sichtbar, rückgängig machbar.

## 4. Leere Zustände und erste Schritte
- **Neues Projekt:** keine leere Übersicht, sondern Checkliste „Erste Schritte“ mit Häkchen:
  1. „Website prüfen“ – ein Knopf, sinnvolle Standards (500 Seiten, robots beachten, Website+Sitemap), Hinweis „ca. 3 Min.“. Einstellungen als Link „anpassen“.
  2. „Google-Positionen verbinden“ – optional; zwei Wege: Anleitung (`docs/anleitung-gsc.md` in der UI, Schritt für Schritt) oder „Mit Testdaten ausprobieren“.
  3. „Erste Seite optimieren“ – Startseite + Keyword-Vorschlag aus Title vorbefüllt.
- **Crawl läuft:** Fortschritt (Seiten, Zeit, aktuelle URL), erste Funde live („bisher 3 defekte Links“), Seite darf verlassen werden.
- **Modul ohne Daten:** 1 Satz „Das zeigt dir dieses Modul“, ausgegrautes Beispielbild, was fehlt, **ein** Knopf. Nie eine leere Tabelle.
- **Ohne GSC:** Positionen sagt ehrlich „Ohne Search Console keine echten Rankings – Google gibt sie nur dem Website-Besitzer.“ Testdaten-Modus: gelbes Band oben auf jeder Positionen-Seite, nicht nur ein Badge.
- **On-Page ohne Crawl:** läuft, aber Zeile „Interne Links und Ladezeit unbekannt → erst Technik-Check“.
- **Fehler** (IP-Sperre, Timeout): Klartext + was tun („Server blockt gerade, in 30 Min. erneut, Pause erhöhen“).

## 5. Was Semrush schlecht macht – und wir besser
1. **Zahlen ohne Reihenfolge** (Errors/Warnings/Notices) → priorisierte Aufgaben mit Wirkung (hoch / mittel / gering).
2. **Jargon ohne Erklärung** (Canonical, hreflang, Striking Distance, KD %) → Klartext-Titel, Fachbegriff klein dahinter, „?“-Tooltip mit 1 Satz + Beispiel.
3. **Widersprüchliche Kennzahlen** (Health hoch, trotzdem „Tausende Issues“) → nur gewichtete Probleme zählen; Notices heißen „Hinweise“.
4. **Issue-Detail = nackte URL-Liste** → pro Seite der konkrete Befund (aktueller Title, Länge) und ein Vorschlag; Gruppierung nach Pfad.
5. **Setup-Wizard mit vielen Fragen vorab** → ein Feld (Domain), gute Standards, Einstellungen später.
6. **50+ Tools, Daten doppelt an vielen Stellen** → 6 Module, jedes mit einer Frage; Module verlinken sich gegenseitig (Kontextaktionen).
7. **Kein „warum hat sich Health geändert“** → Änderungsliste je Crawl („+2: defekte Links behoben, −1: 3 neue lange Titles“).
8. **Kein Erledigt-Gefühl** → Fortschrittsleiste und grüne Häkchen nach Neu-Crawl.
9. **Modals, Upsell, Limits** → keine; alles inline (HTMX), jede Ansicht hat eine teilbare URL.

## 6. Wireframes

### Projekt-Startseite (Übersicht)
```
+-------------------+--------------------------------------------------------------+
| [beispiel.de      v] |  beispiel.de                     Stand: 15.10., 18:05  [Neu prüfen]|
|                   |--------------------------------------------------------------|
| > Übersicht       |  WAS JETZT TUN                  Seit 01.10.: 4/9 erledigt ███░ |
|   Technik-Check   |  1 Doppelte Inhalte zusammenführen  8 Seiten  mittel  +2,1 [>] |
|   Ladezeit        |  2 Meta-Descriptions eindeutig     2 Seiten  leicht  +1,4 [>] |
|   Positionen      |  3 Falsche URLs aus Sitemap        1 Datei   techn.  +1,2 [>] |
|   Keyword-Ideen   |  4 Glossar-Seiten ausbauen       116 Seiten  mittel  +0,9 [>] |
|   Seite optim.    |     vermutlich 1 Template: /glossar/*                         |
|                   |  5 Titles kürzen (≤ 70 Zeichen)   22 Seiten  leicht  +0,6 [>] |
|                   |  weitere 4 anzeigen · Feinschliff (11) · ausgeblendet (0)     |
|                   |  ✓ erledigt seit letztem Crawl: Defekte interne Links (5)     |
|                   |--------------------------------------------------------------|
|                   |  [Technik 96 % ↑2] [Ladezeit mobil 62 ↓] [Positionen Ø 14 ↑] |
|                   |  "1 neues Problem"  "3 Seiten zu langsam" "12 fast Seite 1"   |
| ⚙ Einstellungen   |                                                               |
+-------------------+--------------------------------------------------------------+
```

### Issue-Detail (eigene Seite, nicht nur aufklappen)
```
Technik-Check > Aufgaben > Titles kürzen
+----------------------------------------------------------------------------+
| Titles kürzen (≤ 70 Zeichen)        Warnung · leicht · Wirkung gering      |
| Warum: Google schneidet lange Titles ab, der Klick-Grund geht verloren.    |
| So geht's: 1. Wichtigstes Wort nach vorn  2. Firmenname kürzen/weglassen    |
|            3. Im CMS: Feld "SEO-Titel"                                      |
| Verlauf: 31 → 22 Seiten (↓ besser)        [Bewusst so]  [Als CSV]          |
|----------------------------------------------------------------------------|
| Gruppe /glossar/* (18)  ·  Rest (4)                     Sortierung: Länge v |
| Seite                       Befund                      Aktion             |
| /glossar/llm-agent          84 Z.: "Was ist ein LLM-…"  [Seite] [Optimieren]|
| /glossar/prompt-chaining    79 Z.: "Prompt Chaining …"  [Seite] [Optimieren]|
| ...                                                                        |
|                                      [Nur diese 22 Seiten neu prüfen]      |
+----------------------------------------------------------------------------+
```

### On-Page-Ergebnis
```
Seite optimieren > beispiel.de/  · Keyword "ki agentur"            [Neu prüfen]
+------------------+------------------+--------------------------------------+
| SEO-Score  65 ↑8 | KI-Score   54    | Title  "Beispiel – …"  · 1 H1 · 640 W.  |
| gegen letzte Pr. | zitierfähig?     | Links rein: 42 · LCP mobil 3,1 s     |
+------------------+------------------+--------------------------------------+
| ZUERST DIESE 3                                                            |
| 1 [hoch] Keyword in den Title                                             |
|     jetzt: "Beispiel – Digitale Lösungen"                                    |
|     z. B.: "KI-Agentur Beispiel – Digitale Lösungen"                [kopieren]|
| 2 [hoch] Keyword im ersten Absatz nennen   jetzt: erst nach 230 Wörtern   |
| 3 [mittel] FAQ-Block mit 3 Fragen          Fragen unten ↓                 |
| weitere Ideen (6)                                                         |
|---------------------------------------------------------------------------|
| > Begriffe, die fehlen (7/15)   > FAQ-Fragen (5)   > KI-Suche (4 offen)   |
| > Mitbewerber (0 – URL hinzufügen)   > Alle Prüfungen (32, 21 ✓)          |
+---------------------------------------------------------------------------+
```
