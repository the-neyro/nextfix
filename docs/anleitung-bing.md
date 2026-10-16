# Bing Webmaster Tools anbinden (API-Schlüssel)

Einmalig ca. 5 Minuten, kostenlos. Ein Schlüssel gilt für alle Websites im eigenen Bing-Konto.

## 1. Website in Bing Webmaster Tools

1. <https://www.bing.com/webmasters> öffnen, mit Microsoft-, Google- oder Facebook-Konto anmelden.
2. Website hinzufügen. Am schnellsten: **Import aus der Google Search Console** (übernimmt Websites samt Bestätigung).
   Sonst über Meta-Tag, XML-Datei oder DNS bestätigen.
3. Für Kundenseiten: Kunde fügt dich in seinem Bing-Konto als Nutzer hinzu (Einstellungen → Benutzerverwaltung),
   oder er bestätigt die Seite in deinem Konto.

## 2. API-Schlüssel

1. Oben rechts **Einstellungen (Zahnrad) → API-Zugriff**, Nutzungsbedingungen lesen und annehmen.
2. **API-Schlüssel generieren**. Es gibt nur einen Schlüssel pro Nutzer.
3. Schlüssel als einzige Zeile in eine Textdatei legen (außerhalb des Projekts, kommt nie ins Git):

```bash
mkdir -p ~/.config/seo-tool && pbpaste > ~/.config/seo-tool/bing-api-key.txt && chmod 600 ~/.config/seo-tool/bing-api-key.txt
```

(Vorher den Schlüssel in Bing kopieren. Anderer Ort: Umgebungsvariable `SEO_BING_SCHLUESSEL=/pfad/zur/datei.txt`.)

Der Schlüssel ist ein Passwort: nicht in Chats, Mails oder Screenshots. Bei Verdacht in Bing löschen und neu erzeugen.

## 3. Im Tool

1. Projekt → Tab **Positionen** → „Zugang Bing Webmaster Tools“ → **Verbindung testen**. Die passende Website wird markiert.
2. Quelle **Bing Webmaster** → **Importieren**, oder „Täglich automatisch: Bing“ einschalten.
3. Oben zwischen **Google** und **Bing** umschalten. Die Daten werden nie zusammengerechnet.

Per MCP: `gsc_status(projekt_id, quelle="bing")` → `gsc_test(..., quelle="bing")` →
`positionen_import(projekt_id, quelle="bing")` → `positionen_uebersicht(..., suchmaschine="bing")`.

## Grenzen (anders als bei Google)

- Nur die **Top-Suchbegriffe**, nicht alle.
- **Wochenwerte** (ein Datum pro Woche), keine Tageswerte. Bing aktualisiert wöchentlich.
- Keine Seiten, Länder oder Geräte pro Suchbegriff → keine Kannibalisierung, kein Länder-/Gerätefilter.
- Ein API-Aufruf liefert die gesamte verfügbare Historie; der Auto-Import fragt höchstens alle 20 Stunden.
- Der Schlüssel steht in der Anfrage-URL (so verlangt es Bing); das Tool schreibt URLs deshalb nie in Fehlermeldungen.
