-- Datenbankschema. Wird beim Start idempotent ausgeführt.

CREATE TABLE IF NOT EXISTS projekte (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    domain      TEXT NOT NULL UNIQUE,
    angelegt_am TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Crawl-Einstellungen, eine Zeile pro Projekt
CREATE TABLE IF NOT EXISTS einstellungen (
    projekt_id     INTEGER PRIMARY KEY REFERENCES projekte(id) ON DELETE CASCADE,
    start_url      TEXT,                 -- leer = https://<domain>/
    seitenlimit    INTEGER NOT NULL DEFAULT 500,
    crawl_delay    REAL    NOT NULL DEFAULT 0.5,   -- Sekunden zwischen Abrufen
    user_agent     TEXT    NOT NULL DEFAULT 'SeoToolBot/0.1 (+lokal)',
    robots_beachten INTEGER NOT NULL DEFAULT 1,
    quelle         TEXT    NOT NULL DEFAULT 'website',  -- website | sitemap
    -- Listen, ein Eintrag pro Zeile (siehe app/crawler/filter.py)
    erlauben       TEXT    NOT NULL DEFAULT '',   -- nur diese Pfad-Masken crawlen
    sperren        TEXT    NOT NULL DEFAULT '',   -- diese Pfad-Masken nicht crawlen
    parameter_entfernen TEXT NOT NULL DEFAULT '', -- URL-Parameter, die ignoriert werden ("*" = alle)
    checks_aus     TEXT    NOT NULL DEFAULT ''    -- Check-IDs, die nicht ausgewertet werden
);

CREATE TABLE IF NOT EXISTS crawls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_id    INTEGER NOT NULL REFERENCES projekte(id) ON DELETE CASCADE,
    status        TEXT NOT NULL DEFAULT 'laeuft',  -- laeuft | fertig | abgebrochen | fehler
    gestartet_am  TEXT NOT NULL DEFAULT (datetime('now')),
    beendet_am    TEXT,
    start_url     TEXT NOT NULL,
    seiten_anzahl INTEGER NOT NULL DEFAULT 0,
    robots_status INTEGER,     -- HTTP-Status von /robots.txt (NULL = nicht abrufbar)
    robots_text   TEXT,
    sitemap_urls  TEXT,        -- in robots.txt genannte Sitemaps, Zeilen
    sitemap_status INTEGER,    -- Status der ersten Sitemap bzw. /sitemap.xml
    health        REAL,
    fehler_text   TEXT,
    abbrechen     INTEGER NOT NULL DEFAULT 0,
    lebenszeichen TEXT,         -- letzte Aktivität des Crawlers; alt = Crawl-Prozess tot
    quelle        TEXT NOT NULL DEFAULT 'website',  -- Crawl-Quelle zum Zeitpunkt des Crawls
    fakten        TEXT,         -- JSON: Site-weite Fakten (HTTPS, www, TLS, llms.txt), siehe app/crawler/site.py
    checks_aus    TEXT NOT NULL DEFAULT ''  -- beim Start ausgeschlossene Checks (zählen nicht zum Health Score)
);

CREATE TABLE IF NOT EXISTS seiten (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id         INTEGER NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    url              TEXT NOT NULL,
    tiefe            INTEGER NOT NULL,
    status_code      INTEGER,          -- NULL = Abruf fehlgeschlagen
    abruf_fehler     TEXT,
    redirect_ziel    TEXT,
    content_type     TEXT,
    content_encoding TEXT,
    ladezeit_ms      INTEGER,
    html_bytes       INTEGER,
    blockiert        INTEGER NOT NULL DEFAULT 0,   -- durch robots.txt
    -- Inhalt (nur bei HTML)
    title            TEXT,
    meta_description TEXT,
    h1_anzahl        INTEGER,
    h1_text          TEXT,
    canonical_anzahl INTEGER,
    canonical        TEXT,
    meta_robots      TEXT,
    x_robots_tag     TEXT,
    woerter          INTEGER,
    text_anteil      REAL,             -- Text/HTML-Verhältnis 0..1
    hat_viewport     INTEGER,
    viewport_ok      INTEGER,
    hat_doctype      INTEGER,
    hat_charset      INTEGER,
    hat_meta_refresh INTEGER,
    lang             TEXT,
    hat_frames       INTEGER,
    hat_hsts         INTEGER,
    last_modified    TEXT,             -- HTTP-Header Last-Modified
    hat_passwort     INTEGER,
    -- JSON-Felder (Listen/Objekte aus dem Parser)
    hreflang         TEXT,
    markup           TEXT,
    signatur         TEXT,             -- MinHash des Haupttextes (Duplicate Content)
    plugins          TEXT,
    semantik         TEXT,
    lesbarkeit       TEXT,
    kaputte_links    TEXT,
    link_rank        INTEGER,          -- interne Link-Stärke 0–100 (app/core/linkrank.py)
    geo              TEXT,             -- JSON: Signale für KI-Suche (app/crawler/geo.py)
    blockierend      TEXT,             -- JSON: externe Skripte im <head> ohne async/defer
    UNIQUE (crawl_id, url)
);

-- Links und Ressourcen, die auf einer Seite gefunden wurden
CREATE TABLE IF NOT EXISTS links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id   INTEGER NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    seite_id   INTEGER NOT NULL REFERENCES seiten(id) ON DELETE CASCADE,
    ziel_url   TEXT NOT NULL,
    art        TEXT NOT NULL,      -- a | img | script | css
    intern     INTEGER NOT NULL,
    anker_text TEXT,
    nofollow   INTEGER NOT NULL DEFAULT 0,
    alt        TEXT                -- nur img; NULL = Attribut fehlt
);
CREATE INDEX IF NOT EXISTS idx_links_crawl ON links(crawl_id, ziel_url);

-- Geprüfte Ressourcen: interne Bilder/JS/CSS und externe Ziele (Links, Bilder, JS, CSS)
CREATE TABLE IF NOT EXISTS ressourcen (
    crawl_id         INTEGER NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    url              TEXT NOT NULL,
    art              TEXT NOT NULL,      -- a | img | script | css
    status_code      INTEGER,            -- NULL = nicht erreichbar
    extern           INTEGER NOT NULL DEFAULT 0,
    -- nur interne JS/CSS (per GET geladen)
    bytes            INTEGER,            -- entpackte Größe
    content_encoding TEXT,
    gecacht          INTEGER,
    minifiziert      INTEGER,            -- NULL = zu klein zum Bewerten
    PRIMARY KEY (crawl_id, url)
);

CREATE TABLE IF NOT EXISTS issues (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id INTEGER NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    check_id TEXT NOT NULL,
    seite_id INTEGER REFERENCES seiten(id) ON DELETE CASCADE,  -- NULL = betrifft die ganze Site
    detail   TEXT
);
CREATE INDEX IF NOT EXISTS idx_issues_crawl ON issues(crawl_id, check_id);

-- Sitemap-Dateien (inkl. Index-Dateien) eines Crawls
CREATE TABLE IF NOT EXISTS sitemap_dateien (
    crawl_id   INTEGER NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    url        TEXT NOT NULL,
    status     INTEGER,
    bytes      INTEGER NOT NULL DEFAULT 0,
    url_anzahl INTEGER NOT NULL DEFAULT 0,
    ist_index  INTEGER NOT NULL DEFAULT 0,
    fehler     TEXT
);

-- URLs aus Sitemaps; status_code nur für URLs, die der Crawl nicht selbst abgerufen hat
CREATE TABLE IF NOT EXISTS sitemap_eintraege (
    crawl_id    INTEGER NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    sitemap_url TEXT NOT NULL,
    status_code INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sitemap_eintraege ON sitemap_eintraege(crawl_id, url);

-- Search-Console-Daten (Position Tracking), eigenes Archiv pro Projekt.
-- Eine Zeile = ein Tag × Suchbegriff × Seite × Land × Gerät, wie die GSC-API sie liefert.
CREATE TABLE IF NOT EXISTS gsc_zeilen (
    projekt_id   INTEGER NOT NULL REFERENCES projekte(id) ON DELETE CASCADE,
    datum        TEXT    NOT NULL,   -- YYYY-MM-DD
    query        TEXT    NOT NULL,
    seite        TEXT    NOT NULL,
    land         TEXT    NOT NULL,   -- ISO-3166 alpha-3 klein, z. B. deu
    geraet       TEXT    NOT NULL,   -- DESKTOP | MOBILE | TABLET
    klicks       INTEGER NOT NULL,
    impressionen INTEGER NOT NULL,
    position     REAL    NOT NULL,   -- Ø-Position laut Google (1 = ganz oben)
    quelle       TEXT    NOT NULL,   -- gsc | mock
    PRIMARY KEY (projekt_id, datum, query, seite, land, geraet)
);
CREATE INDEX IF NOT EXISTS idx_gsc_query ON gsc_zeilen(projekt_id, query, datum);

-- Tracking-Liste: Suchbegriffe, die im Position Tracking zählen (wie die Keyword-Liste in Semrush)
CREATE TABLE IF NOT EXISTS tracking_keywords (
    projekt_id  INTEGER NOT NULL REFERENCES projekte(id) ON DELETE CASCADE,
    query       TEXT    NOT NULL,   -- klein geschrieben, wie GSC sie liefert
    angelegt_am TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (projekt_id, query)
);

CREATE TABLE IF NOT EXISTS tracking_tags (
    projekt_id INTEGER NOT NULL,
    query      TEXT    NOT NULL,
    tag        TEXT    NOT NULL,
    PRIMARY KEY (projekt_id, query, tag),
    FOREIGN KEY (projekt_id, query) REFERENCES tracking_keywords(projekt_id, query) ON DELETE CASCADE
);

-- Search-Console-Zugang je Projekt (der Schlüssel selbst liegt außerhalb der DB, siehe config.GSC_SCHLUESSEL)
CREATE TABLE IF NOT EXISTS gsc_einstellungen (
    projekt_id INTEGER PRIMARY KEY REFERENCES projekte(id) ON DELETE CASCADE,
    property   TEXT NOT NULL   -- z. B. sc-domain:example.de oder https://www.example.de/
);

-- Importläufe (Hand oder automatisch), laufen im Hintergrund wie Crawls
CREATE TABLE IF NOT EXISTS gsc_importe (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_id   INTEGER NOT NULL REFERENCES projekte(id) ON DELETE CASCADE,
    quelle       TEXT    NOT NULL,                  -- gsc | mock
    ausloeser    TEXT    NOT NULL DEFAULT 'hand',   -- hand | auto
    status       TEXT    NOT NULL DEFAULT 'laeuft', -- laeuft | fertig | fehler
    von          TEXT    NOT NULL,
    bis          TEXT    NOT NULL,
    tage_gesamt  INTEGER NOT NULL,
    tage_fertig  INTEGER NOT NULL DEFAULT 0,
    zeilen       INTEGER NOT NULL DEFAULT 0,
    property     TEXT,
    fehler_text  TEXT,
    gestartet_am TEXT    NOT NULL DEFAULT (datetime('now')),
    beendet_am   TEXT,
    lebenszeichen TEXT
);

-- Täglicher Auto-Import: Zeile vorhanden = an
CREATE TABLE IF NOT EXISTS gsc_auto (
    projekt_id INTEGER PRIMARY KEY REFERENCES projekte(id) ON DELETE CASCADE,
    quelle     TEXT NOT NULL                        -- gsc | mock
);

-- Property/Website je Projekt und Quelle (gsc, bing). Ersetzt gsc_einstellungen (wird hierher übernommen).
CREATE TABLE IF NOT EXISTS quelle_properties (
    projekt_id INTEGER NOT NULL REFERENCES projekte(id) ON DELETE CASCADE,
    quelle     TEXT    NOT NULL,
    property   TEXT    NOT NULL,
    PRIMARY KEY (projekt_id, quelle)
);
INSERT OR IGNORE INTO quelle_properties (projekt_id, quelle, property)
    SELECT projekt_id, 'gsc', property FROM gsc_einstellungen;
DELETE FROM gsc_einstellungen;

-- Auto-Import je Projekt und Suchmaschine (höchstens eine Quelle pro Suchmaschine). Ersetzt gsc_auto.
CREATE TABLE IF NOT EXISTS auto_importe (
    projekt_id   INTEGER NOT NULL REFERENCES projekte(id) ON DELETE CASCADE,
    suchmaschine TEXT    NOT NULL,   -- google | bing
    quelle       TEXT    NOT NULL,   -- gsc | mock | bing | bing_mock
    PRIMARY KEY (projekt_id, suchmaschine)
);
INSERT OR IGNORE INTO auto_importe (projekt_id, suchmaschine, quelle)
    SELECT projekt_id, 'google', quelle FROM gsc_auto;
DELETE FROM gsc_auto;

-- Phase 5: Keyword-Recherche (wie Keyword Magic Tool): ein Hauptbegriff → viele Ideen
CREATE TABLE IF NOT EXISTS recherchen (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_id    INTEGER NOT NULL REFERENCES projekte(id) ON DELETE CASCADE,
    seed          TEXT    NOT NULL,
    sprache       TEXT    NOT NULL DEFAULT 'de',
    land          TEXT    NOT NULL DEFAULT 'de',
    status        TEXT    NOT NULL DEFAULT 'laeuft',   -- laeuft | fertig | fehler
    schritte_fertig INTEGER NOT NULL DEFAULT 0,
    schritte_gesamt INTEGER NOT NULL DEFAULT 0,
    ideen         INTEGER NOT NULL DEFAULT 0,
    fehler_text   TEXT,
    angelegt_am   TEXT    NOT NULL DEFAULT (datetime('now')),
    beendet_am    TEXT,
    lebenszeichen TEXT
);

CREATE TABLE IF NOT EXISTS recherche_ideen (
    recherche_id     INTEGER NOT NULL REFERENCES recherchen(id) ON DELETE CASCADE,
    keyword          TEXT    NOT NULL,
    quellen          TEXT    NOT NULL,   -- suggest, gsc (mit Komma)
    intent           TEXT    NOT NULL,   -- informational | kommerziell | transaktional | navigational
    gruppe           TEXT    NOT NULL,
    woerter          INTEGER NOT NULL,
    frage            INTEGER NOT NULL DEFAULT 0,
    gsc_impressionen INTEGER,            -- eigene Daten der letzten 90 Tage (Google), falls vorhanden
    gsc_klicks       INTEGER,
    gsc_position     REAL,
    PRIMARY KEY (recherche_id, keyword)
);

-- Antworten von Google Suggest, damit dieselbe Anfrage nicht ständig wiederholt wird
CREATE TABLE IF NOT EXISTS suggest_cache (
    anfrage      TEXT NOT NULL,
    sprache      TEXT NOT NULL,
    land         TEXT NOT NULL,
    antwort      TEXT NOT NULL,   -- JSON-Liste
    abgerufen_am TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (anfrage, sprache, land)
);

-- Suchvolumen-Cache (Bing GetKeywordStats), 30 Tage gültig
CREATE TABLE IF NOT EXISTS volumen_cache (
    keyword      TEXT NOT NULL,
    land         TEXT NOT NULL,
    sprache      TEXT NOT NULL,
    quelle       TEXT NOT NULL,   -- bing | bing_mock
    monat        INTEGER,         -- NULL = Bing kennt den Begriff nicht
    verlauf      TEXT NOT NULL,   -- JSON: Wochenwerte, älteste zuerst
    abgerufen_am TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (keyword, land, sprache, quelle)
);

-- Core Web Vitals (Labor, Playwright): ein Messlauf je Crawl, ausgewählte Seiten × Geräte
CREATE TABLE IF NOT EXISTS vitals_laeufe (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id      INTEGER NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    status        TEXT    NOT NULL DEFAULT 'laeuft',  -- laeuft | fertig | fehler
    fertig        INTEGER NOT NULL DEFAULT 0,
    gesamt        INTEGER NOT NULL,
    fehler_text   TEXT,
    gestartet_am  TEXT    NOT NULL DEFAULT (datetime('now')),
    beendet_am    TEXT,
    lebenszeichen TEXT
);

CREATE TABLE IF NOT EXISTS vitals (
    lauf_id  INTEGER NOT NULL REFERENCES vitals_laeufe(id) ON DELETE CASCADE,
    url      TEXT    NOT NULL,
    geraet   TEXT    NOT NULL,   -- mobile | desktop
    ttfb     INTEGER, fcp INTEGER, lcp INTEGER, cls REAL, tbt INTEGER,
    bytes    INTEGER, anfragen INTEGER, score INTEGER, fehler TEXT,
    PRIMARY KEY (lauf_id, url, geraet)
);

-- On-Page SEO Checker: eine Prüfung = Seite × Keyword (Ergebnis als JSON, für Verlauf und MCP)
CREATE TABLE IF NOT EXISTS onpage_pruefungen (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_id  INTEGER NOT NULL REFERENCES projekte(id) ON DELETE CASCADE,
    url         TEXT    NOT NULL,
    keyword     TEXT    NOT NULL,
    score       INTEGER NOT NULL,
    ergebnis    TEXT    NOT NULL,
    angelegt_am TEXT    NOT NULL DEFAULT (datetime('now'))
);
