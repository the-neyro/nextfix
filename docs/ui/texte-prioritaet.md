# UI-Texte und Priorisierung „Was jetzt tun“

Grundlage: `app/checks/*`, `app/core/score.py`, Templates `_uebersicht.html`, `issues.html`, `positionen.html`, `_onpage_ergebnis.html`, `_crawl_status.html`.
Regeln: du-Form, aktiv, Handlung zuerst, Satzanfang groß, keine Füllwörter. Ein Ding = ein Wort, überall.

## 1. Wortschatz

Größtes Problem heute: Mischsprache (Issues, Crawl, Health, Notices) und Synonyme für dasselbe (Keyword / Suchbegriff / Begriff, Prüfung / Check / Crawl). Badges zeigen rohe Werte wie `error`.

| Alt | Neu | Warum |
|---|---|---|
| Error / Warning / Notice | **Dringend / Wichtig / Feinschliff** | Sagt, wann man handeln soll, nicht wie „schlimm“ ein Fehler technisch ist |
| Schweregrad | Dringlichkeit | passt zu den drei Stufen |
| Kategorie | Bereich | alltagsnah |
| Site Health / Health Score | **Website-Zustand** (z. B. „78 von 100“) | „Health“ ist Jargon, Prozent klingt nach Messung, Punkte nach Note |
| Issue | **Problem** (Liste), **Aufgabe** (Startseite „Was jetzt tun“) | Problem = was gefunden wurde, Aufgabe = was du tust |
| Treffer | Fundstelle | „Treffer“ klingt positiv |
| Crawl (Substantiv) | **Prüfung** („Prüfung vom 14.10.“) | Nutzer will Ergebnis, nicht Technik |
| crawlen / Audit starten | **Website prüfen** | Verb aus Nutzersicht |
| Gecrawlte Seiten | Geprüfte Seiten | s. o. |
| Crawler, Bot | Suchmaschinen-Bot (Tooltip) | bleibt verständlich mit Zusatz |
| Site Audit | Website-Check | Tab-Name |
| On-Page SEO Checker | Seiten-Check | ein Check pro URL + Suchbegriff |
| Keyword / Begriff | **Suchbegriff** (immer) | heute drei Wörter für eins |
| Tracking-Liste, tracken | **Beobachtete Suchbegriffe**, beobachten | Tracking klingt nach Überwachung von Personen |
| Striking Distance / „Fast auf Seite 1“ | **Fast auf Seite 1** (Platz 8–20) | ist schon gut, beibehalten |
| Kannibalisierung | **Mehrere Seiten für einen Suchbegriff** | Metapher erklärt nichts |
| Intent | **Suchabsicht** (Info / Kaufen / Ort / Marke) | deutsches Wort reicht |
| Impressionen | Einblendungen | „wie oft du im Suchergebnis zu sehen warst“ |
| CTR | Klickrate | |
| Ø Position | Ø Platz | Platz 1 = ganz oben, intuitiv |
| Gewinner / Verlierer | Aufsteiger / Absteiger | bezieht sich auf Platz, nicht Menschen |
| Redirect, 301/302 | Weiterleitung (dauerhaft / vorübergehend) | Code nur im Detail |
| 4xx / 5xx | Seite nicht gefunden (404) / Serverfehler (500) | Zahl in Klammern für Fachleute |
| Anchor-Text | Linktext | |
| Minifiziert | verkleinert | |
| Render-blockierend | bremst den Seitenaufbau | |
| Mixed Content | Unsichere Inhalte auf HTTPS-Seite | |
| Crawl-Budget | (streichen) | für kleine Sites irrelevant, verwirrt nur |
| E-E-A-T, GEO | (streichen) → „Vertrauen“, „KI-Suche“ | Quelle ggf. im Tooltip |
| Ideen (On-Page) | Verbesserungen | „Ideen“ klingt unverbindlich |

**Fachbegriffe, die bleiben dürfen** (Tooltip-Text, 1 Satz):

- **Title:** Der Seitentitel, den Google als blaue Überschrift im Suchergebnis zeigt.
- **Meta-Description:** Der kurze Text unter dem Titel im Suchergebnis; überzeugt Leute zum Klicken.
- **H1:** Die Hauptüberschrift auf der Seite selbst.
- **Canonical:** Ein Hinweis an Google, welche von mehreren ähnlichen Adressen die Hauptversion ist.
- **noindex:** Eine Anweisung an Suchmaschinen, die Seite nicht im Suchergebnis zu zeigen.
- **robots.txt:** Datei im Hauptordner der Website, die Bots sagt, was sie lesen dürfen.
- **Sitemap (sitemap.xml):** Liste aller wichtigen Seiten, damit Suchmaschinen nichts übersehen.
- **llms.txt:** Kurze Übersichtsdatei für KI-Assistenten wie ChatGPT oder Perplexity.
- **hreflang:** Verknüpft Sprachversionen einer Seite, damit jeder Besucher die richtige sieht.
- **Strukturierte Daten (JSON-LD):** Unsichtbare Zusatzinfos, die Google z. B. Sterne oder Preise anzeigen lassen.
- **HTTPS / Zertifikat:** Verschlüsselte Verbindung, erkennbar am Schloss im Browser.
- **Sichtbarkeit:** Wie präsent du bei deinen Suchbegriffen bist; 100 % = überall Platz 1.
- **Core Web Vitals (LCP, CLS, TBT):** Googles Messwerte dafür, wie schnell und ruhig eine Seite lädt.
- **Suchvolumen:** Wie oft ein Begriff pro Monat gesucht wird (geschätzt).

## 2. Priorisierung „Was jetzt tun“

Ziel: eine Liste mit 3–7 Aufgaben, sortiert nach „Nutzen pro Aufwand“. Keine Zählerkacheln.

**Formel je Check mit Fundstellen** (alle Werte liegen schon vor: Schwere, betroffene Seiten, ganze Site, geprüfte Seiten):

```
S = 10 (error) | 4 (warning) | 1 (notice)
R = 1,0                         wenn ganze Site
  = 0,3 + 0,7 · √(betroffen / geprüft)   sonst
A = 1 Einstellung (einmal für alle Seiten: Server, Plugin, Template, robots.txt)
  = 2 Je Seite kurz (Titel, Beschreibung, Link, alt-Text, Weiterleitung)
  = 3 Je Seite Text (schreiben, zusammenlegen, umbauen)
Priorität = round(10 · S · R / A)          → 0 … 100
```

- **S** anders als `score.py` (dort Notice = 0): Feinschliff darf auf der Liste auftauchen, landet aber hinten.
- **√** dämpft: 10 % der Seiten zählt schon spürbar, 100 % nicht zehnmal so viel.
- **A** neues Feld `aufwand` im Katalog (Default je Bereich: technik/https/performance/crawlbarkeit = 1, links = 2, inhalt/ki = 3; einzelne Checks überschreiben, z. B. title_* = 2, externe_links_defekt = 2).
- Zweites neues Feld `wer`: **„Machst du selbst“** (im CMS) oder **„Für deine Technik“** (Hoster/Entwickler:in). Laien wollen wissen, ob sie es selbst können.
- Nicht in die Liste: reine Info-Checks (`blockiert`, `x_robots_noindex`, `ki_training_bots_blockiert`, `externe_nofollow`), die nur „Prüfen, ob gewollt“ sagen. Die kommen als **„Bitte kurz prüfen“** unten drunter.
- Gruppen: **Jetzt** (Priorität ≥ 30 oder irgendein „Dringend“), **Als Nächstes** (10–29), **Wenn Zeit ist** (< 10). Startseite zeigt „Jetzt“ + die ersten 3 aus „Als Nächstes“.
- Gleichstand: zuerst „Machst du selbst“, dann mehr Seiten.

**Muster je Aufgabe:** `Verb + Was + Anzahl` · `Nutzen in einem Halbsatz` · Badge Aufwand + Wer.
Kein „Du solltest“, kein Passiv, Zahl immer mit Einheit („22 Seiten“).

**8 Beispiele** (angenommen 200 geprüfte Seiten):

| Prio | Aufgabe (Titel) | Nutzen-Zeile | Aufwand · Wer |
|---|---|---|---|
| 15 | Repariere 2 Links auf fremde Seiten, die nicht mehr existieren | Besucher landen nicht mehr im Leeren | 2 Min. · selbst |
| 15 | Führe 8 fast gleiche Seiten zusammen | Google zeigt dann die richtige Version statt keiner | groß · selbst |
| 11 | Erweitere 112 Seiten mit wenig Text (unter 200 Wörter) | Mehr Text beantwortet mehr Suchanfragen | groß · selbst |
| 11 | Kürze den Titel von 22 Seiten auf 70 Zeichen | Google schneidet den Titel nicht mehr ab | klein · selbst |
| 10 | Lass JS- und CSS-Dateien verkleinern (182 Seiten) | Seiten laden schneller, ein Plugin reicht | klein · Technik |
| 3 | Verlinke 40 Seiten von weiteren eigenen Seiten | Google findet und gewichtet sie besser | mittel · selbst |
| 3 | Kürze die Beschreibung von 29 Seiten auf 160 Zeichen | Deine Botschaft bleibt im Suchergebnis vollständig | klein · selbst |
| 2 | Belege 37 Texte mit Zahlen oder Quellen | KI-Antworten zitieren belegte Texte häufiger | groß · selbst |

Rechnung Beispiel `wenig_text`: S=4, R=0,3+0,7·√0,56=0,82, A=3 → 10·4·0,82/3 = 11.
Bei vielen Seiten: Aufgabe zeigt die 5 wichtigsten URLs (meiste Einblendungen aus GSC, sonst geringste Klicktiefe) + „alle 112 zeigen“.
Neues Katalog-Feld `aufgabe` (Vorlage mit `{n}`) statt Titel zur Laufzeit zu basteln; Name bleibt für die Problemliste.

## 3. Check-Texte: Stichprobe

Gelesen: ~25 Checks. **Gut** (verständlich, Handlung klar): `title_zu_lang`, `meta_desc_zu_kurz`, `wenig_text`, `externe_links_defekt`, `duplicate_content`, `zertifikat_ablauf`, `ki_bots_blockiert`, `llms_tote_links`, `www_aufloesung`, `bilder_ohne_alt`.
**Auch schwach**, aber nicht Top 10: `status_5xx` („Server-Logs prüfen“ kann kein Laie), `ohne_last_modified`, `interne_links_nofollow`, `ki_artikel_ohne_autor_datum` (E-E-A-T), `zu_viele_parameter` (Crawl-Budget).

**Die 10 schwächsten, neu formuliert** (Name / Warum / Beheben):

1. **nicht_erreichbar** – alt: „Seiten nicht crawlbar“, Ursache statt Folge.
   Neu: *Seiten laden nicht oder zu langsam* / Diese Seiten antworteten nicht innerhalb von 5 Sekunden. Besucher und Google sehen nur eine Fehlermeldung. / Öffne die Seiten selbst im Browser. Laden sie auch dort nicht, gib die Liste an deinen Hoster.
2. **blockiert** – alt: „Vom Crawling blockiert“ / „Prüfen, ob das gewollt ist.“ (vage).
   Neu: *Seiten für Google gesperrt* / Diese Seiten erscheinen nie im Suchergebnis, weil robots.txt oder „noindex“ sie sperrt. / Geh die Liste durch: Login, Warenkorb, Danke-Seiten dürfen gesperrt sein. Alles andere entsperren lassen.
3. **perm_redirect** – alt: „Permanente Weiterleitungen“, Warum mit „Crawl-Budget“.
   Neu: *Interne Links zeigen auf alte Adressen* / Die Links führen über eine Weiterleitung zum Ziel. Das kostet bei jedem Klick Ladezeit. / Ändere den Link so, dass er direkt auf die neue Adresse zeigt.
4. **kein_hsts** – alt: „Kein HSTS“, Abkürzung ohne Erklärung.
   Neu: *Browser erzwingen keine sichere Verbindung* / Beim allerersten Aufruf kann die Verbindung noch unverschlüsselt sein. / Lass deinen Hoster den Header „Strict-Transport-Security“ einschalten (eine Einstellung).
5. **mixed_content** – alt: „Mixed Content“.
   Neu: *Unsichere Inhalte auf sicheren Seiten* / Die Seite läuft über HTTPS, lädt aber Bilder oder Skripte über HTTP. Browser blockieren sie oder zeigen eine Warnung. / Ersetze in den Adressen dieser Dateien „http://“ durch „https://“.
6. **text_html_niedrig** – alt: „Niedriges Text/HTML-Verhältnis (≤ 10 %)“, Kennzahl ohne Bedeutung.
   Neu: *Viel Code, wenig Text* / Weniger als 10 % der Seite ist lesbarer Text, der Rest ist Code. Oft lädt sie dadurch langsamer. / Füge Text hinzu. Bleibt der Wert niedrig, lass prüfen, welche Skripte und Styles überflüssig sind.
7. **h1_gleich_title** – alt: Warning, Begründung „zusätzliche Keywords“ ist fragwürdig.
   Neu: *Überschrift und Titel sind identisch* / Kein Fehler. Unterschiedliche Formulierungen decken aber mehr Suchvarianten ab. / Formuliere die Überschrift auf der Seite etwas anders als den Titel. (Schwere auf „Feinschliff“ senken.)
8. **js_css_nicht_minifiziert** – alt: Fachwort im Namen.
   Neu: *Skript- und Style-Dateien nicht verkleinert* / Leerzeichen und Kommentare machen die Dateien größer, die Seite lädt langsamer. / Aktiviere ein Optimierungs-Plugin (z. B. Autoptimize bei WordPress) oder gib den Punkt an deine Technik.
9. **skripte_blockierend** – alt: „Render-blockierende Skripte im \<head\>“ + TBT.
   Neu: *Skripte bremsen den Seitenaufbau* / Diese Skripte laden, bevor die Seite etwas zeigt. Besucher sehen länger eine weiße Fläche. / Lade Chat, Tracking und ähnliche Skripte später (Attribut „defer“). Das kann deine Technik in Minuten.
10. **canonical_defekt** – alt: „nicht mit 200 antwortet“.
   Neu: *Hauptversion zeigt auf eine kaputte Seite* / Der Canonical verweist auf eine Adresse, die einen Fehler liefert oder weiterleitet. Google ignoriert den Hinweis. / Trage als Canonical die richtige, funktionierende Adresse ein (meist die Seite selbst).

Generell: „Warum“ beschreibt die **Folge für Besucher oder Google**, nicht die Technik. „Beheben“ beginnt mit Verb und nennt bei Server-Themen „Hoster/Technik“ als Adressat.

## 4. Buttons, leere Zustände, Meldungen

**Buttons** (Verb + Objekt, immer gleich):

| Alt | Neu |
|---|---|
| Audit starten | Website prüfen |
| Abbrechen (laufender Crawl) | Prüfung abbrechen |
| Prüfen (On-Page) | Seite prüfen |
| Anlegen | Projekt anlegen |
| Importieren | Daten abrufen |
| Volumen holen (max. 200) | Suchvolumen abrufen |
| Ideen suchen | Suchbegriffe finden |
| Angekreuzte tracken / Tag setzen | Auswahl beobachten |
| Aus Tracking-Liste nehmen | Nicht mehr beobachten |
| CSV-Export / Alle Issues als CSV | Als CSV herunterladen |
| PDF-Bericht | Bericht als PDF |
| Filtern | (weglassen, Filter sofort anwenden) |
| {Quelle} löschen | {Quelle}-Daten löschen; Rückfrage: „Alle Daten aus {Quelle} löschen? Das lässt sich nicht rückgängig machen.“ |

**Leere Zustände** (sagen, was fehlt + nächster Schritt):

- Keine Projekte: „Noch keine Website angelegt. Trag deine Domain ein und starte die erste Prüfung.“
- Projekt ohne Prüfung: „Diese Website wurde noch nicht geprüft. Die erste Prüfung dauert je nach Größe 2–10 Minuten.“ [Website prüfen]
- „Was jetzt tun“ leer: „Alles erledigt. Prüf die Website wieder, wenn du etwas geändert hast.“
- Positionen ohne Daten: „Noch keine Platzierungen. Verbinde die Search Console oder lade zum Ausprobieren Testdaten.“
- Fast auf Seite 1 / Aufsteiger / Absteiger leer: „Gerade keine.“ (statt „keine“ klein)
- Mehrere Seiten für einen Suchbegriff leer: „Gut so: Jeder Suchbegriff hat eine klare Seite.“
- Suchbegriff-Ideen leer: „Keine Vorschläge für diesen Filter. Lockere den Filter oder nimm einen allgemeineren Begriff.“
- Ladezeit nicht gemessen: „Noch nicht gemessen. Die Messung dauert pro Seite etwa 30 Sekunden.“

**Fehlermeldungen** (Was ist passiert. Was du tun kannst.):

- Website nicht erreichbar: „Die Website antwortet nicht. Prüf die Adresse und ob sie im Browser lädt.“
- Server blockt (viele 403/429): „Der Server hat die Prüfung gebremst. Warte ein paar Stunden und prüfe mit längerer Pause zwischen Seiten.“
- Search Console ohne Zugang: „Kein Zugriff auf die Search Console. Trag {E-Mail} dort als Nutzer ein (Berechtigung „Eingeschränkt“).“
- Schlüssel fehlt: „Schlüsseldatei fehlt. Leg sie hier ab: {Pfad}. Anleitung: {Link}.“
- On-Page Zeitüberschreitung: „Die Seite hat zu lange geladen (über 25 Sekunden). Versuch es gleich noch mal.“
- Ungültige URL: „Das ist keine vollständige Adresse. Beispiel: https://example.de/seite“
- Prüfung abgebrochen: „Prüfung abgebrochen nach {n} Seiten. Die Ergebnisse sind unvollständig.“

**Fortschritt und Erfolg** (kurz, mit Zahl, kein „erfolgreich“):

- Läuft: „Prüfe Seite {n} …“ statt „Crawl läuft … {n} Seiten bisher“
- Fertig: „Prüfung fertig: {n} Seiten, {k} Aufgaben für dich.“ [Aufgaben ansehen]
- Daten abgerufen: „{n} Tage Daten abgerufen ({zeilen} Zeilen).“
- Verbindung ok: „Verbindung steht. {n} Websites gefunden.“
- Beobachten: „{n} Suchbegriffe werden jetzt beobachtet.“
- Gespeichert: „Gespeichert.“
- Verlauf: „Seit der letzten Prüfung: {a} Probleme behoben, {b} neu.“
