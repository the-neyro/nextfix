# Datenquellen für Keywords, Rankings, Backlinks, Mitbewerber, Traffic, KI-Sichtbarkeit

Stand: 2026-10-14 · Rahmen: 0 €, keine bezahlten APIs, lokal, praxistauglich für Kundenseiten.
Kennzeichnung: **[F]** = in Primärquelle (Anbieter-Doku) geprüft, **[U]** = unverifiziert (Blog, Dritte, Forum), **[A]** = eigene Annahme/Bewertung.
Empfehlung: **ja** = in der jeweiligen Phase umsetzen, **später** = nach dem Kern, **nein** = nicht verwenden.

## 1. Kurzfazit
- Für **eigene/Kundenseiten** (Zugang zur Search Console) kommen wir sehr nah an Semrush heran, teils besser: echte Klicks, Impressionen, Positionen statt Schätzungen.
- Für **fremde Domains** (Organic Research, Traffic, Keyword-Lücken) fehlt eine legale, kostenlose Quelle für Google-SERPs. Das ist die Hauptlücke.
- Backlinks: Common Crawl liefert einen freien **Domain-Link-Graphen** (wer verlinkt wen, ohne Anker/URL). Seitengenaue Links nur mit großem Aufwand (WAT-Dateien).
- Suchvolumen: absolut nur über Google Ads Keyword Planner (Basic-Zugang nötig, evtl. nur Spannen) oder Bing-Impressionen; sonst relativ (Trends, Wikipedia).

## 2. Quellen im Überblick

### 2.1 Eigene/Kundenseiten (Zugang nötig)

| Quelle | Liefert | Limits/Kosten | Rechtliches/ToS | Qualität | Aufwand | Empf. |
|---|---|---|---|---|---|---|
| **Google Search Console API** (Search Analytics) | Klicks, Impressionen, CTR, Ø-Position je Query/Seite/Land/Gerät/Tag | kostenlos; 25.000 Zeilen pro Anfrage, max. 50.000 Zeilen pro Tag und Suchtyp; 1.200 Anfragen/Min. pro Site; Daten nach 2–3 Tagen [F]; ca. 16 Monate Historie [A, bekannt] | offizielle API, nur verifizierte Properties | sehr hoch (echte Google-Daten), aber Ø-Position statt Momentaufnahme; anonymisierte Queries fehlen | mittel (OAuth oder Service-Account) | **ja (Phase 4)** |
| GSC **URL Inspection API** | Indexstatus, Canonical laut Google, Crawl-Zeit | 2.000 Abfragen/Tag, 600/Min. pro Site [F] | offiziell | hoch | gering | **ja** (Audit-Ergänzung) |
| GSC **Bulk-Export nach BigQuery** | tägliche Rohdaten ohne Zeilenlimit | braucht GCP-Projekt, laut Dritten mit Billing [U] | offiziell | hoch | hoch | **nein** (für kleine Seiten reicht API) |
| GSC **Links-Bericht** | Top-Linkquellen, Ankertexte (Auszug) | keine API [A, API kennt nur searchanalytics/sitemaps/sites/urlInspection] | – | mittel (Stichprobe) | CSV-Import manuell | **später** (CSV-Import) |
| GSC **KI-Bericht** (AI Overviews/AI Mode) | Impressionen in KI-Funktionen je Seite/Land/Gerät, keine Klicks, keine Queries | seit Juni 2026, Rollout-Stand unklar; API-Zugang nicht belegt [U] | offiziell | mittel | unklar | **später** (sobald API) |
| **Bing Webmaster Tools API** | Queries/Seiten-Traffic (GetQueryStats, GetPageStats), eingehende Links (GetLinkCounts, GetUrlLinks), Keyword-Daten für beliebige Begriffe (GetKeyword, GetKeywordStats, GetRelatedKeywords) [F] | kostenlos, API-Key in BWT; Quoten nicht gefunden [U] | offiziell | gut für Bing; Links seitengenau für eigene Sites | gering–mittel | **ja** (Phase 4–6) |
| Bing **AI Performance** | Zitate in Copilot/Bing-KI-Antworten, „Grounding Queries“ | seit Feb. 2026 Preview, nur UI-Export, API „auf Backlog“ [U] | offiziell | einzige echte KI-Zitat-Daten | CSV-Import | **später** (CSV-Import) |
| Google Analytics Data API (GA4) | echte Besuche, Referrer (z. B. chatgpt.com, perplexity.ai) | kostenlos [A] | offiziell, nur mit Kundenzugang | hoch | mittel | **später** |
| Server-Logs des Kunden | Besuche von KI-Crawlern (GPTBot, ClaudeBot, PerplexityBot), Googlebot | 0 € | eigene Daten, DSGVO beachten (IP kürzen) | hoch | mittel (Formate) | **später** |
| Ahrefs Webmaster Tools („Ahrefs Free“) | Backlinks und Keywords eigener verifizierter Sites | kostenlos, ohne API (API nur bezahlt) [U] | Ahrefs-ToS, kein Scraping | hoch | nur manuell/CSV | **nein** für Integration, ok als manueller Abgleich |

Praxis für Kundenseiten: Kunde fügt einen **Service-Account** (E-Mail aus GCP) als Nutzer in der Search Console hinzu. Dann keine OAuth-Token-Abläufe. OAuth-Apps im Status „Testing“ verlieren Refresh-Tokens nach 7 Tagen [A, Google-OAuth-Regel, prüfen].

### 2.2 Keywords, Ideen, Volumen

| Quelle | Liefert | Limits/Kosten | Rechtliches/ToS | Qualität | Aufwand | Empf. |
|---|---|---|---|---|---|---|
| **Google Autocomplete** (inoffizieller Suggest-Endpunkt) | Long-Tail-Ideen, Fragen (A–Z-, W-Fragen-Erweiterung), pro Sprache/Land | kein dokumentiertes Limit, Sperren bei Masse [U] | undokumentiert, keine eigenen Nutzungsbedingungen; Google-ToS verbieten automatisierten Zugriff entgegen robots.txt [F] → **Grauzone** | gut für Ideen, kein Volumen | gering | **ja**, nur sparsam (Cache, Pausen, wenige hundert Abfragen pro Recherche) |
| Bing-/YouTube-/Amazon-Suggest | weitere Ideen, Kauf-/Video-Intent | wie oben [U] | Grauzone wie oben | ergänzend | gering | **später** |
| **Search-Console-Queries** | echte Suchbegriffe, mit denen die Seite schon erscheint | siehe 2.1 | offiziell | sehr hoch | vorhanden ab Phase 4 | **ja** (Basis für Ideen + Chancen auf Pos. 8–20) |
| **Google Ads Keyword Planner API** (KeywordPlanIdeaService) | Ideen + Ø monatliches Volumen, Wettbewerb, Gebotsspannen | kostenlos, aber Ads-Manager-Konto + Developer-Token mit **Basic Access** nötig (Explorer/Test reichen nicht, Prüfung ca. 2 Werktage) [F/U]; ohne Werbebudget evtl. nur Volumen-Spannen [U, Stand 2016] | offiziell; Nutzungszweck „Keyword-Recherche“ ist zulässig [F] | Volumen = Googles eigene Schätzung, gröber bei kleinen Keywords | mittel–hoch (Antrag) | **ja, als Versuch** in Phase 5; Fallback ohne Volumen einplanen |
| **Bing Keyword-Daten** (GetKeywordStats/GetKeyword) | wöchentliche Bing-Impressionen je Begriff/Land/Sprache | kostenlos [F] | offiziell | absolute Zahlen, aber Bing-Markt; Hochrechnung auf Google nur grob [A] | gering | **ja** (Ersatz-Volumen) |
| **Google Trends** offizielle API | Zeitreihen 5 Jahre, nicht auf 0–100 skaliert, mehr als 5 Begriffe | Alpha, nur auf Antrag, keine Preise, ca. 48 h Verzug [U] | offiziell | gut für Saison/Trend | Antrag stellen | **später** (Antrag jetzt stellen) |
| Trends über pytrends & Co. | relative Kurven 0–100 | pytrends seit 2025 archiviert, 429-Sperren [U] | Scraping, Grauzone | instabil | mittel | **nein** (höchstens manuell) |
| **Wikipedia-Seitenaufrufe** (Wikimedia Analytics API) | tägliche Aufrufe pro Artikel/Sprache als Interessen-Proxy | kostenlos, User-Agent mit Kontakt Pflicht, Rate-Limits beachten [F/U] | offen, erlaubt | gut für Themen/Entitäten, nicht für Long-Tail | gering | **ja** (Trend-Ersatz, Themen) |
| **Wikidata** | Entitäten, Synonyme, Sprachvarianten, verwandte Begriffe | kostenlos (SPARQL) [A] | CC0 | gut für Themencluster | gering | **später** |
| Eigener Crawler auf Mitbewerber-Seiten | Titel/H1/Begriffe (n-Gramme) als Keyword-Ideen | 0 € | robots.txt achten, höflich crawlen | gut für Themenlücken | vorhanden | **ja** |

### 2.3 Rankings fremder Domains / SERP

| Quelle | Liefert | Limits/Kosten | Rechtliches/ToS | Qualität | Aufwand | Empf. |
|---|---|---|---|---|---|---|
| **Google-SERP selbst abfragen** (httpx/Playwright) | Top-10/100, SERP-Features, Mitbewerber | seit Jan. 2025 JavaScript-Pflicht + Bot-Schutz („SearchGuard“) [U]; schnell gesperrt | Google-ToS: kein automatisierter Zugriff entgegen robots.txt [F]; robots.txt sperrt `/search` [A]; Google klagt seit Dez. 2025 gegen SerpApi (DMCA, laut einer Quelle im Juli 2026 vorerst abgewiesen) [U] | hoch, wenn es läuft | hoch, fragil | **nein** (kein Umgehen von Schutzmaßnahmen); höchstens manuelle Einzelprüfung im normalen Browser |
| Google Custom Search JSON API | Websuche-Ergebnisse | 100 Abfragen/Tag frei, **für Neukunden geschlossen, Ende 1.1.2027** [U, mehrfach berichtet] | offiziell | weicht von echter SERP ab | – | **nein** |
| Brave Search API | eigener Brave-Index | ca. 5 $ Gratisguthaben/Monat (~1.000 Abfragen), **Kreditkarte nötig** [U] | offiziell | anderer Index als Google | gering | **nein** (Karte/Kostenrisiko); evtl. später als KI-Grounding-Quelle |
| SearXNG / DuckDuckGo-HTML | Meta-Suche | 0 € | fragt Google/Bing per Scraping ab → gleiche ToS-Probleme [A] | instabil | mittel | **nein** |
| SerpBear (Open Source, MIT [A]) | Rank Tracker + GSC-Anbindung + Volumen über Google Ads | braucht Scraper-Dienst oder Proxys für Positionen [U] | – | Ideenquelle | – | **später** als UI-/Konzept-Vorlage |

### 2.4 Backlinks, Autorität, Mitbewerber, Traffic

| Quelle | Liefert | Limits/Kosten | Rechtliches/ToS | Qualität | Aufwand | Empf. |
|---|---|---|---|---|---|---|
| **Common Crawl Web Graph** (Host- und Domain-Ebene) | Kanten „Domain A verlinkt Domain B“, Rang-Datei mit Harmonic Centrality + PageRank; Release ca. alle 1–3 Monate (zuletzt Mai–Juli 2026: 118 Mio. Domains, 2,8 Mrd. Kanten) [F] | 0 €, Download mehrere GB (Kanten-Datei ~16 GB laut Erfahrungsbericht [U]) | Common-Crawl-Nutzungsbedingungen, frei nutzbar [A] | gut für **verweisende Domains** und Autorität; keine URLs, Anker, nofollow; Hosting-Plattformen verzerren [U] | mittel (DuckDB, einmal pro Release filtern) | **ja (Phase 6)** |
| Common Crawl **Columnar Index** (Parquet) | welche URLs einer Domain existieren/gecrawlt wurden | 0 €, Abfrage per DuckDB über Dateiliste [U] | wie oben | gut für „Top-Seiten“ eines Mitbewerbers ohne eigenen Crawl | mittel | **später** |
| Common Crawl **WAT-Dateien** | seitengenaue Links mit Anker | 0 €, aber sehr große Datenmengen pro Crawl [A] | wie oben | hoch, Stichprobe des Webs | sehr hoch | **später**, nur für wenige Ziel-Domains |
| **Open PageRank** (jetzt bei Keywords Everywhere) | Autoritätswert 0–10 je Domain, Monatshistorie seit 2018, Basis Common Crawl [F] | kostenlos 30.000 Domains/Monat, 100 Domains pro Anfrage, Konto nötig, keine Karte [F] | Anbieter-API | grob, aber praktisch | gering | **ja** (schneller „Authority Score“) |
| **CrUX** (Chrome UX Report, BigQuery) | Popularitäts-Bucket je Origin (Top 1k/10k/…/1M), auch je Land, plus Core Web Vitals [F, Stand 2021-Doku] | BigQuery-Sandbox kostenlos mit Monatskontingent [A] | offiziell, offene Daten | grobe Traffic-Klasse, echte Chrome-Nutzung | mittel | **ja** (Traffic-Klasse in Phase 6) |
| **Cloudflare Radar** Domain-Ranking | Top-100 exakt, sonst Buckets bis 1 Mio., wöchentlich [F] | API-Token; Kosten in Doku nicht genannt [U] | offiziell | grob, global | gering | **später** |
| **Tranco-Liste** | täglicher Rang Top 1 Mio., gemittelt aus mehreren Listen [F] | 0 € | Forschungsliste | nur große Seiten | gering | **später** |
| Eigenes Traffic-Modell | Klicks ≈ Volumen × CTR(Position) | 0 € | – | hängt an Volumen + Positionen; öffentliche CTR-Kurven [U] | mittel | **ja** für eigene Keywords, für fremde Domains nur mit SERP-Daten (fehlen) |
| Ahrefs/Majestic/Moz Free-Checker | Backlink-Stichproben fremder Domains | Gratis-Weboberflächen | Scraping verboten | – | – | **nein** |

### 2.5 KI-Sichtbarkeit (GEO)

| Quelle | Liefert | Limits/Kosten | Rechtliches/ToS | Qualität | Aufwand | Empf. |
|---|---|---|---|---|---|---|
| **GEO Optimizer** (Auriti-Labs/geo-optimizer-skill, MIT, Python, CLI + 12 MCP-Tools) [F] | Audit 0–100 (robots.txt für 27 KI-Crawler, llms.txt, JSON-LD, 47 Zitierbarkeits-Checks), Fix-Vorschläge, Verlauf; `geo citations` fragt KI-Dienste mit eigenen Keys [F] | Audit ohne Key; Zitat-Tests nur mit Keys (Perplexity, OpenAI, Gemini, Groq …) [F] | MIT → Ideen/Code übernehmbar mit Lizenzhinweis | Audit-Teil solide; Zitat-Teil schwankt je Lauf | gering (als Vorlage) | **ja** als Vorlage für eigene GEO-Checks im Site Audit |
| Gemini API Free Tier mit Google-Search-Grounding | Antwort + zitierte Quellen-URLs → „wird die Marke/Domain zitiert?“ | Gratiskontingent unklar: 1.500 Anfragen/Tag (2.5 Flash) bzw. 5.000/Monat (Gemini 3) laut Forum [U] | offizielle API; Free-Tier-Daten können zum Training genutzt werden [A, prüfen] | Näherung an AI Overviews, nicht identisch | gering | **später** (kleine, feste Prompt-Liste, mehrere Läufe) |
| Freie LLM-APIs ohne Websuche (Groq u. a.) / lokales Ollama | nur Modellwissen über die Marke | Free Tiers [U] / 0 € lokal | offiziell | spiegelt nicht ChatGPT-Antworten | gering | **später**, nur als „Markenwissen“-Check |
| ChatGPT/Perplexity-Weboberfläche automatisieren | echte Antworten | – | ToS-Verstoß | – | – | **nein** |
| Bing AI Performance / GSC KI-Bericht / Logs / GA4-Referrer | echte Zitate, Impressionen, Besuche | siehe 2.1 | offiziell | beste verfügbare Wahrheit | CSV/API | **ja**, sobald Kundenzugang besteht |

### 2.6 Open-Source-Vorbilder
- **OpenSEO** (every-app/open-seo, MIT): Keywords, Rank Tracking, Backlinks, Mitbewerber, KI-Sichtbarkeit, MCP – aber alles über **DataForSEO (bezahlt)**, keine freie Alternative [F]. Nur Konzept-/UI-Vorlage.
- **SerpBear**: zeigt, wie GSC-Daten pro Keyword neben Positionen angezeigt werden; Volumen über Google Ads mit Basic Access [F].
- **GEO Optimizer**: siehe 2.5.

## 3. Empfohlene Reihenfolge

### Phase 4 – Position Tracking (eigene/Kundenseiten)
1. GSC-Anbindung per Service-Account (Fallback OAuth), Properties auflisten, Zugriff je Projekt.
2. Täglicher Abruf Search Analytics (Query × Seite × Land × Gerät), **eigenes Archiv** in SQLite – damit Historie länger als 16 Monate.
3. Tracking-Liste: Keywords aus GSC wählen oder manuell anlegen; Ø-Position, Klicks, Impressionen, CTR; Visibility-Score nach eigener Formel (CTR-Kurve × Impressionen) [A].
4. Auswertungen: Gewinner/Verlierer, Kannibalisierung (mehrere URLs pro Query), „Striking Distance“ (Pos. 8–20).
5. Bing Webmaster API als zweite Suchmaschine; URL Inspection für Indexstatus der getrackten Seiten.
6. Später: CSV-Import GSC-KI-Bericht und Bing AI Performance.
Hinweis in der UI: Positionen sind Google-Durchschnitte, keine täglichen Momentaufnahmen wie bei Semrush; Mitbewerber-Positionen fehlen.

### Phase 5 – Keyword Research
1. Ideen: GSC-Queries + Google-Suggest-Erweiterung (gedrosselt, Cache) + Begriffe aus Mitbewerber-Crawl.
2. Volumen: Bing GetKeywordStats sofort; parallel Google-Ads-Basic-Access beantragen und Keyword Planner anbinden, falls bewilligt (Spannen sauber anzeigen).
3. Trend/Saison: Wikipedia-Pageviews jetzt, Antrag für die offizielle Trends-API stellen.
4. Clustering (eigene Ähnlichkeit, MinHash ist vorhanden) und Intent nach Regeln (Fragewörter, „kaufen“, „preis“ …) [A].
5. Keyword Difficulty nur eingeschränkt: ohne SERP-Daten keine echte KD. Ersatz: Ziel-URL-Autorität (Open PageRank/CC-Rang) vs. eigene [A].

### Phase 6 – Backlinks, Mitbewerber, Domain-Übersicht
1. Common Crawl Domain-Graph pro Release lokal laden, nach Projekt- und Mitbewerber-Domains filtern → verweisende Domains, neu/verloren zwischen Releases, Link-Intersect (Lücken-Analyse).
2. Authority Score: Open PageRank (API) + CC-Harmonic-Centrality/PageRank (Rang-Datei).
3. Eigene Seiten seitengenau: Bing GetUrlLinks + GSC-Links-CSV-Import; Prüfung, ob Links noch live sind, mit eigenem Crawler.
4. Traffic-Klasse fremder Domains: CrUX-Bucket (je Land) + Tranco/Cloudflare-Bucket; eigene Domains: echte GSC-Klicks.
5. Mitbewerber finden: Co-Citation im Link-Graph (gleiche verweisende Domains) + manuell eingetragene Mitbewerber; SERP-basierte Mitbewerber entfallen.
6. Später: WAT-Auswertung für Anker/URLs bei wenigen Ziel-Domains; CC-Columnar-Index für Mitbewerber-Seitenlisten.

## 4. Wo bleibt die Lücke zu Semrush
- **Organic Research fremder Domains**: Für welche Keywords ein Mitbewerber rankt und wie viel Traffic er hat, ist ohne SERP-Datenbank nicht machbar. Das ist die größte Lücke; legale Gratisquelle gibt es nicht.
- **Keyword-Datenbank**: Semrush hat Volumen, KD, CPC, SERP-Features für Milliarden Keywords in vielen Ländern. Wir haben Volumen nur pro Abfrage (Ads/Bing), teils als Spannen, ohne echte KD.
- **Täglich exakte Positionen inkl. Mitbewerber, lokal/mobil, SERP-Features**: nur Ø-Positionen eigener Seiten aus GSC.
- **Backlink-Index**: Semrush seitengenau, mit Anker, täglich aktuell. Wir haben Domain-Ebene, alle 1–3 Monate, Stichprobe von Common Crawl.
- **Traffic Analytics/Market Explorer, PPC-/Werbedaten**: nicht abbildbar, nur grobe Popularitäts-Buckets.
- **KI-Sichtbarkeit über ChatGPT/Perplexity in großem Umfang**: nur Stichproben über freie APIs und die Berichte von Google/Bing.
- **Wo wir vorn liegen können**: echte GSC-/Bing-Daten der Kundenseiten (genauer als Semrush-Schätzungen), tieferes Site Audit, GEO-Audit, lokale Datenhaltung, MCP-Zugriff auf alles.

## 5. Offene Punkte / zu prüfen
- Google-Ads-Basic-Access ohne Werbebudget: echte Zahlen oder nur Spannen? → mit eigenem Konto testen.
- Ob die GSC-API den KI-Bericht liefert; Bing-API-Quoten; Cloudflare-Radar-Kosten; BigQuery-Sandbox für CrUX ohne Billing.
- Datenschutz: GSC-/GA4-Daten von Kunden nur lokal speichern, Zugänge pro Kunde trennen.

## Quellen
- GSC Limits: https://developers.google.com/webmaster-tools/limits
- GSC alle Daten abrufen (Zeilenlimits, Verzug): https://developers.google.com/webmaster-tools/v1/how-tos/all-your-data
- GSC Bulk-Export: https://developers.google.com/search/blog/2023/02/bulk-data-export
- GSC KI-Bericht (Juni 2026): https://ppc.land/google-finally-gives-search-console-its-own-generative-ai-visibility-reports/ , https://www.seo-day.de/news/article/google-search-console-ai-performance-reports-and-controls?lang=en
- Bing Webmaster API (Methodenliste): https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi?view=bing-webmaster-dotnet , https://www.bing.com/webmaster/api/
- Bing AI Performance: https://searchengineland.com/bing-webmaster-tools-testing-new-ai-performance-report-468039 , https://www.searchinfluence.com/blog/bing-ai-performance-report-copilot-citations/
- Google Ads API Zugangsstufen: https://developers.google.com/google-ads/api/docs/access-levels
- Keyword Planner Metriken: https://developers.google.com/google-ads/api/reference/rpc/v22/KeywordPlanHistoricalMetrics
- Volumen-Spannen bei wenig Budget (2016): https://searchengineland.com/google-officially-throttling-keyword-planner-data-low-spending-adwords-accounts-255795
- SerpBear Google-Ads-Anbindung: https://docs.serpbear.com/miscellaneous/integrate-google-ads , https://docs.serpbear.com
- Google Trends API Alpha: https://ppc.land/google-opens-alpha-testing-for-new-trends-api-targeting-developers-and-journalists/ , https://developers.google.com/search/apis/trends
- pytrends archiviert: https://scrapebadger.com/blog/does-google-trends-have-an-api-what-to-use-in-2026
- Google Suggest (inoffiziell): https://growthrocks.com/glossary/googles-query-suggest-api/
- Google Nutzungsbedingungen: https://policies.google.com/terms
- JavaScript-Pflicht Google-Suche: https://gigazine.net/gsc_news/en/20250121-google-requiring-javascript
- Google vs. SerpApi: https://ipwatchdog.com/2025/12/26/google-sues-serpapi-parasitic-scraping-circumvention-protection-measures/ , https://www.searchenginejournal.com/google-files-dmca-suit-targeting-serpapis-serp-scraping/563847/
- Custom Search API Ende 2027: https://brave.com/learn/google-api-shutdown/
- Brave Search API Preise: https://parallel.ai/articles/best-free-web-search-api
- Common Crawl Web Graph: https://commoncrawl.org/blog/host--and-domain-level-web-graphs-may-june-and-july-2026 , https://commoncrawl.org/blog/web-graph-statistics-gets-a-proper-upgrade
- Backlink-Analyse mit CC + DuckDB (Erfahrungsbericht): https://www.indiehackers.com/post/how-i-did-backlink-gap-analysis-for-free-with-common-crawl-duckdb-cafa669c54
- Open PageRank: https://keywordseverywhere.com/openpagerank
- CrUX Popularität: https://developer.chrome.com/blog/crux-rank-magnitude
- Cloudflare Radar Rankings: https://developers.cloudflare.com/radar/investigate/domain-ranking-datasets/
- Tranco: https://tranco-list.eu/
- Wikimedia API Zugriff: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html
- Ahrefs Webmaster Tools: https://ahrefs.com/webmaster-tools
- Gemini Grounding Free Tier (Forum): https://discuss.ai.google.dev/t/grounding-free-quota-clarifying-2026-rules-for-gemini-2-5-flash-paid-tier-1/144593
- GEO Optimizer: https://github.com/Auriti-Labs/geo-optimizer-skill
- OpenSEO: https://github.com/every-app/open-seo
