# PDF-Berichte (Vorlage: Semrush „Domain-Übersicht“)

Quelle: vom Nutzer bereitgestelltes PDF-Beispiel (Domain-Übersicht Desktop, 1. Juli 2026, 8 Seiten, A4 hoch).
Nur Aufbau übernommen, kein Layout, keine Marke, keine Texte.

## Aufbau des Beispiels

| Seite | Inhalt |
|---|---|
| 1 | Deckblatt: Berichtsname, Domain, Datum |
| 2 | Zusammenfassung organisch (Traffic, Rang, Keywords, Traffic-Kosten mit Veränderung in %), bezahlt (gleich), Backlinks (gesamt, verweisende Domains/IPs); Ringdiagramme „Keywords nach Land“; Liniendiagramm organisch vs. bezahlt über die Jahre |
| 3 | Traffic-Verlauf organisch, Top-Keywords (Keyword, Position, Suchvolumen, Traffic-Anteil), Verteilung der Positionen (Balken 1–3, 4–10 …), Keywords nach Suchintention, Top-Mitbewerber |
| 4 | Mitbewerber-Tabelle (gemeinsame Keywords, Wettbewerbsgrad), Positionierungskarte (Blasendiagramm Keywords × Traffic), Marken- vs. generischer Traffic |
| 5–6 | Bezahlte Suche: Verlauf 12 Monate, Top-Keywords mit CPC, Anzeigenpositionen, Mitbewerber, Positionierungskarte, Anzeigenbeispiel |
| 7–8 | Backlinks: Top-Backlinks, Follow vs. Nofollow, Linktypen (Text/Bild/Frame/Formular), Top verweisende Domains mit IP/Land |

Wiederkehrende Bausteine: Kopf mit Logo + Absender, Fußzeile „Generiert am … / Seite n“, je Block Titel + Kontextzeile
(Land | Domain | Name), KPI-Zahl groß mit Veränderungs-Badge, Ring-, Linien-, Balken-, Blasendiagramm, Tabellen.

## Was wir davon liefern können

| Teil | Daten bei uns | Wann |
|---|---|---|
| Site-Audit-PDF (Health, Kategorien, Top-Issues, Themen, Vergleich) | vorhanden | zuerst |
| Organisch (Keywords, Positionen, Traffic) | nur eigene Domains über Search Console | nach Phase 4 |
| Keywords nach Land, Suchintention | Search Console + eigene Einordnung | nach Phase 5 |
| Bezahlte Suche, CPC, Anzeigen | keine freie Quelle (Google-Ads-Konto nötig) | offen |
| Backlinks, Mitbewerber | keine freie Quelle in dieser Größe | offen |

## Technik (Entscheidung offen)

HTML-Vorlage (Jinja, wie die Web-UI) → PDF. Optionen:
- Headless Chromium (Playwright): gleiche Darstellung wie im Browser, braucht Installation (~150 MB).
- WeasyPrint: reines Python, braucht Systembibliotheken (pango) per Homebrew.
Diagramme als inline-SVG, damit sie in jedem PDF-Weg scharf bleiben.
