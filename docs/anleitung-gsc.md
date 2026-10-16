# Search Console anbinden (Service-Account)

Einmalig ca. 10 Minuten, kostenlos, keine Abrechnung bei Google nötig.
Danach reicht für jede weitere Website (auch Kundenseiten): Service-Account-Adresse in deren Search Console eintragen.

## 1. Google-Cloud-Projekt und API

1. <https://console.cloud.google.com/> öffnen, oben „Projekt auswählen“ → **Neues Projekt** (Name z. B. `seo-tool`).
2. **APIs & Dienste → Bibliothek** → „Google Search Console API“ suchen → **Aktivieren**.

## 2. Service-Account und Schlüssel

1. **IAM & Verwaltung → Dienstkonten → Dienstkonto erstellen**. Name `seo-tool`, Rollen überspringen (keine nötig).
2. Das neue Dienstkonto öffnen → Reiter **Schlüssel** → **Schlüssel hinzufügen → Neuen Schlüssel erstellen → JSON**.
   Die Datei wird heruntergeladen.
   - Mit einem Firmen-Workspace-Konto kann das per Richtlinie gesperrt sein (`iam.disableServiceAccountKeyCreation`).
     Dann ein privates Google-Konto nehmen oder den Admin fragen.
3. Datei an den Ort legen, den das Tool erwartet (außerhalb des Projekts, kommt so nie ins Git):

```bash
mkdir -p ~/.config/seo-tool && mv ~/Downloads/seo-tool-*.json ~/.config/seo-tool/gsc-service-account.json && chmod 600 ~/.config/seo-tool/gsc-service-account.json
```

Anderer Ort: Umgebungsvariable `SEO_GSC_SCHLUESSEL=/pfad/zur/datei.json`.

Der Schlüssel ist ein Passwort: nicht weitergeben, nicht in Chats oder Mails kopieren. Bei Verlust in der Cloud Console löschen und neu erstellen.

## 3. Zugriff in der Search Console

1. <https://search.google.com/search-console> → Property wählen → **Einstellungen → Nutzer und Berechtigungen → Nutzer hinzufügen**.
2. Die Adresse des Service-Accounts eintragen (steht in der JSON-Datei als `client_email`
   und im Tool unter Positionen → „Search-Console-Zugang“), Berechtigung **Eingeschränkt**.
3. Für Kundenseiten: Kunde trägt dieselbe Adresse in seiner Search Console ein. Mehr ist nicht nötig.

## 4. Im Tool

1. Projekt → Tab **Positionen** → „Search-Console-Zugang“ → **Verbindung testen**.
   Die passende Property wird markiert (Domain-Property `sc-domain:` hat Vorrang vor URL-Präfix).
   Nur bei Bedarf eine Property von Hand eintragen.
2. Falls Testdaten da sind: **Testdaten löschen**.
3. Quelle **Search Console**, Tage wählen (max. 480, Google hält ca. 16 Monate vor) → **Importieren**.
   Pro Tag eine Anfrage, 90 Tage dauern also etwa eine Minute.

Per MCP: `gsc_status` → `gsc_test` → `positionen_import(projekt_id, quelle="gsc", tage=480)`.

## Grenzen

- Daten kommen mit 2–3 Tagen Verzug; der Import endet deshalb standardmäßig vor 3 Tagen.
- Positionen sind Durchschnitte laut Google, keine Momentaufnahmen.
- Seltene Suchanfragen anonymisiert Google; sie fehlen in den Zeilen (Summen sind daher etwas kleiner als in der GSC-Oberfläche).
- Kontingent: 1.200 Anfragen pro Minute und Website, das reicht locker.
