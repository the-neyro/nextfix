# Site Audit: Check-Liste (Vorbild Semrush)

Quelle: öffentliches Semrush-Hilfe-Center, „What Issues Can Site Audit Identify?“
(https://www.semrush.com/kb/542-site-audit-issues-list), abgerufen 2026-10-14.
Nur Namen und Schwellenwerte übernommen, eigene Formulierung.

Spalte **MVP**: ✅ = in Version 1, ⏳ = später, ❌ = braucht externe Daten/Dienste.

## Errors (kritisch)

| Check | Kriterium | MVP |
|---|---|---|
| 4xx-Statuscode | Seite antwortet 4xx | ✅ |
| 5xx-Statuscode | Seite antwortet 5xx | ✅ |
| Title fehlt | fehlend oder leer | ✅ |
| Doppelter Title | exakt gleich | ✅ |
| Doppelte Meta-Description | exakt gleich | ✅ |
| Doppelter Content | ≥ 85 % identisch | ⏳ |
| Defekte interne Links | Ziel 4xx/5xx | ✅ |
| Defekte interne Bilder | Ziel nicht erreichbar | ✅ |
| Defekte interne JS/CSS | Ziel nicht erreichbar | ✅ |
| Nicht crawlbar: Timeout/Zugriff | Antwort > 5 s oder verweigert | ✅ |
| Nicht crawlbar: DNS | Hostname löst nicht auf | ✅ |
| Nicht crawlbar: ungültige URL | URL-Syntax kaputt | ✅ |
| Malformed Links | ungültige Link-Syntax | ✅ |
| robots.txt Formatfehler | Syntax | ✅ |
| sitemap.xml Formatfehler | XML/Schema | ✅ |
| Falsche Seiten in Sitemap | Redirects, Duplikate, Non-200 | ✅ |
| Sitemap zu groß | > 50 MB unkomprimiert oder > 50.000 URLs | ✅ |
| WWW-Auflösung | www/non-www nicht vereinheitlicht | ✅ |
| Viewport-Tag fehlt | kein `meta viewport` | ✅ |
| Viewport-Breite fehlt | kein `width` / `initial-scale` | ✅ |
| HTML zu groß | > 2 MB | ✅ |
| Langsame Seite | nur HTML-Ladezeit gemessen | ✅ |
| Redirect-Ketten/-Schleifen | > 3 Redirects oder Loop | ✅ |
| Meta-Refresh | Tag vorhanden | ✅ |
| Defekter Canonical | Ziel nicht 200 | ✅ |
| Mehrere Canonicals | > 1 Canonical | ✅ |
| Mixed Content | HTTPS lädt HTTP-Ressourcen | ✅ |
| HTTP → HTTPS fehlt | kein Redirect/Canonical auf HTTPS-Startseite | ✅ |
| Passwortfeld auf HTTP | unsichere Seite | ✅ |
| Zertifikat abgelaufen/läuft ab | Ablaufdatum | ✅ |
| Falscher Zertifikatsname | CN/SAN passt nicht | ✅ |
| Veraltetes Protokoll | SSL oder TLS 1.0 | ⏳ |
| Unsichere Cipher (Subdomains) | schwache Verschlüsselung | ⏳ |
| hreflang-Konflikte | vs. Canonical, widersprüchlich, ohne Selbstreferenz | ⏳ |
| hreflang-Werte falsch | nicht ISO 639-1 / ISO 3166-1 alpha-2 | ⏳ |
| hreflang-Links fehlerhaft | nicht absolut oder nicht 200 | ⏳ |
| Ungültige strukturierte Daten | Schema verletzt | ⏳ |
| AMP ohne Canonical / AMP-HTML/Style/Template | AMP-Validierung | ❌ |

## Warnings

| Check | Kriterium | MVP |
|---|---|---|
| Title zu lang | > 70 Zeichen | ✅ |
| Title zu kurz | ≤ 10 Zeichen | ✅ |
| Meta-Description fehlt | – | ✅ |
| H1 fehlt | – | ✅ |
| H1 = Title | identisch | ✅ |
| Wenig Text | < 200 Wörter | ✅ |
| Text/HTML-Verhältnis niedrig | ≤ 10 % | ✅ |
| Bilder ohne alt | – | ✅ |
| Temporäre Redirects | 302 / 307 | ✅ |
| Defekte externe Links / Bilder | Ziel 4xx/5xx | ✅ |
| Interne Links mit nofollow | – | ✅ |
| Zu viele Links auf Seite | > 3.000 | ✅ |
| Zu viele URL-Parameter | > 4 | ✅ |
| Unterstriche in URL | – | ✅ |
| Link-URL zu lang | > 2.000 Zeichen | ✅ |
| Ohne hreflang und lang | – | ✅ |
| Ohne Zeichenkodierung | kein charset | ✅ |
| Ohne Doctype | – | ✅ |
| Frames | `frame`/`iframe`-Layout | ✅ |
| Plugin-Inhalte | Flash, Java Applet, Silverlight | ✅ |
| sitemap.xml fehlt | – | ✅ |
| Sitemap nicht in robots.txt | – | ✅ |
| HTTP-URLs in Sitemap bei HTTPS | – | ✅ |
| Startseite ohne HTTPS | – | ✅ |
| HTTPS-Seite verlinkt HTTP | – | ✅ |
| Unkomprimierte Seiten | kein `Content-Encoding` | ✅ |
| Unkomprimierte JS/CSS | – | ✅ |
| Ungecachte JS/CSS | keine Cache-Header | ✅ |
| Unminifizierte JS/CSS | Heuristik | ⏳ |
| JS/CSS gesamt zu groß | > 2 MB | ✅ |
| Zu viele JS/CSS-Dateien | > 100 | ✅ |
| Interne Ressourcen per robots.txt blockiert | – | ✅ |
| Subdomains ohne SNI | – | ⏳ |

## Notices

| Check | Kriterium | MVP |
|---|---|---|
| robots.txt fehlt | – | ✅ |
| Mehr als ein H1 | – | ✅ |
| URL zu lang | > 200 Zeichen | ✅ |
| Permanente Redirects | 301 / 308 | ✅ |
| Klicktiefe | > 3 Klicks von Startseite | ✅ |
| Nur ein interner Link eingehend | – | ✅ |
| Orphaned Pages (Sitemap) | in Sitemap, nicht verlinkt | ✅ |
| Orphaned Pages (Google Analytics) | braucht GA-Daten | ❌ |
| Externe nofollow-Links | – | ✅ |
| Links ohne Anchor-Text | – | ✅ |
| Nicht aussagekräftiger Anchor | „hier“, „mehr“ … (Liste) | ✅ |
| Links auf externe 403 | – | ✅ |
| Vom Crawling blockiert | robots.txt / meta robots | ✅ |
| X-Robots-Tag noindex | Header | ✅ |
| Externe Ressourcen per robots.txt blockiert | – | ⏳ |
| Defekte externe JS/CSS | – | ✅ |
| Ressource als Seitenlink | `<a href="x.css">` o. ä. | ✅ |
| hreflang-Sprachabweichung | Sprache ≠ hreflang | ⏳ |
| Subdomains ohne HSTS | Header fehlt | ✅ |
| Veralteter Inhalt | `Last-Modified` > 6 Monate | ✅ |
| llms.txt fehlt / Formatfehler | AI Search | ✅ |
| Zu viel Inhalt (AI Search) | Schwelle unbekannt | ⏳ |
| Wenig semantisches HTML (AI Search) | Heuristik | ⏳ |
| Inhalt nicht optimiert | Überschriften, Absatzlänge, Lesbarkeit | ⏳ |

## Umsetzung (Stand 2026-10-14)

- 53 Checks umgesetzt, Quelle der Wahrheit ist `app/checks/` (`.venv/bin/python -c "from app.checks import REGISTER; print(len(REGISTER))"`).
- Eigene Festlegungen, wo Semrush keine Zahl nennt:
  - Langsame Seite: HTML-Antwort > 1 s (zwischen 1 und 5 s; > 5 s = „nicht crawlbar“).
  - Redirect-Kette: mehr als 3 Weiterleitungen oder Schleife.
  - Nicht aussagekräftiger Anchor: feste Liste („hier“, „mehr“, „click here“ …) in `app/checks/links.py`.
  - HSTS: nur an der ersten HTTPS-Seite geprüft, als Site-Problem gewertet.
- Noch offen aus der ✅-Liste: robots.txt-/Sitemap-Formatfehler, falsche Seiten in Sitemap, Orphans aus Sitemap, WWW-Auflösung, HTTP→HTTPS-Redirect, Zertifikat, Passwortfeld auf HTTP, externe Links/Bilder prüfen, JS/CSS-Größe/Anzahl/Caching/Kompression, Plugin-Inhalte, llms.txt, veralteter Inhalt, Ressource als Seitenlink.

## Fazit für das MVP

- Rund 80 % der Checks gehen mit **Crawler + HTML-Parser + HTTP-Header + TLS-Abfrage** – ohne externe Dienste.
- Später: Duplicate Content (Ähnlichkeitsvergleich), hreflang-Logik, Structured-Data-Validierung, TLS-Details.
- Weglassen: AMP, Google-Analytics-Abgleich.
- Schweregrad-Modell übernehmen: Error / Warning / Notice, plus Kategorie (Crawlability, HTTPS, Performance, Links, Markup …).
