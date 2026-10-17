"""Checks auf Site-Ebene: HTTPS-Weiterleitung, www, Zertifikat, robots.txt-Format, KI-Suche."""


from app.checks.katalog import check, fakten
from app.crawler.robots import RobotsTxt

ROBOTS_FELDER = {"user-agent", "allow", "disallow", "sitemap", "crawl-delay", "host", "clean-param",
                 "request-rate", "visit-time", "noindex", "content-signal"}

# Crawler von KI-Suchdiensten (Antworten mit Quellen), nicht reine Trainings-Crawler
# (Google-Extended steuert die Quellen-Nutzung in Gemini; Applebot-Extended nur Training, daher nicht dabei)
KI_SUCH_BOTS = ("OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Perplexity-User", "Claude-SearchBot",
                "Claude-User", "Google-Extended", "DuckAssistBot", "MistralAI-User")
# Reine Trainings-Crawler: Sperre ist eine bewusste Entscheidung, daher nur als Hinweis
KI_TRAINING_BOTS = ("GPTBot", "ClaudeBot", "CCBot", "Applebot-Extended", "Meta-ExternalAgent", "Bytespider",
                    "Amazonbot", "cohere-training-data-crawler")
LLMS_MIN_LINKS = 3


def robots_pruefen(text: str) -> list[str]:
    """Formatfehler in robots.txt: unbekannte Felder, fehlender Doppelpunkt, Regeln vor User-agent."""
    fehler, hat_agent = [], False
    for nr, zeile in enumerate(text.splitlines(), 1):
        inhalt = zeile.split("#", 1)[0].strip()
        if not inhalt:
            continue
        if ":" not in inhalt:
            fehler.append(f"Zeile {nr}: kein Doppelpunkt: {inhalt[:60]}")
            continue
        feld = inhalt.split(":", 1)[0].strip().lower()
        if feld not in ROBOTS_FELDER:
            fehler.append(f"Zeile {nr}: unbekanntes Feld „{feld}“")
        elif feld == "user-agent":
            hat_agent = True
        elif feld in ("allow", "disallow") and not hat_agent:
            fehler.append(f"Zeile {nr}: {feld} vor dem ersten User-agent")
    return fehler


@check("robots_formatfehler", "Formatfehler in robots.txt", "error", "crawlbarkeit",
       "Fehlerhafte Zeilen werden von Suchmaschinen ignoriert, Sperren greifen evtl. nicht.",
       "Nur gültige Felder (User-agent, Allow, Disallow, Sitemap …) im Format 'Feld: Wert' verwenden.")
def robots_formatfehler(conn, crawl_id):
    z = conn.execute("SELECT robots_text FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    return [(None, f) for f in robots_pruefen(z[0] or "")]


@check("http_nicht_auf_https", "HTTP leitet nicht auf HTTPS um", "error", "https",
       "Die HTTP-Version ist erreichbar, ohne auf HTTPS weiterzuleiten: doppelte Inhalte, unsichere Aufrufe.",
       "http:// per 301 auf die https://-Version umleiten.")
def http_nicht_auf_https(conn, crawl_id):
    f = fakten(conn, crawl_id).get("http_zu_https")
    return [(None, f"{f['start']} → {f.get('url')}")] if f and not f.get("ok") else []


@check("www_aufloesung", "WWW-Auflösung uneinheitlich", "error", "crawlbarkeit",
       "Mit und ohne www. sind getrennt erreichbar: Suchmaschinen sehen zwei Websites mit gleichem Inhalt.",
       "Eine Variante wählen und die andere per 301 dorthin umleiten.")
def www_aufloesung(conn, crawl_id):
    f = fakten(conn, crawl_id).get("www")
    return [(None, f"{f['start']} → {f.get('url')} (Haupt: {f.get('haupt')})")] if f and not f.get("ok") else []


@check("zertifikat_ablauf", "Zertifikat abgelaufen oder läuft bald ab", "error", "https",
       "Ein abgelaufenes Zertifikat blockiert Besucher mit einer Browser-Warnung.",
       "Zertifikat erneuern bzw. automatische Erneuerung (z. B. Let's Encrypt) prüfen.")
def zertifikat_ablauf(conn, crawl_id):
    from app.crawler.site import ZERTIFIKAT_WARNUNG_TAGE
    t = fakten(conn, crawl_id).get("tls") or {}
    if t.get("abgelaufen"):
        return [(None, "abgelaufen" + (f" am {t['ablauf']}" if t.get("ablauf") else ""))]
    if t.get("rest_tage") is not None and t["rest_tage"] < ZERTIFIKAT_WARNUNG_TAGE:
        return [(None, f"läuft in {t['rest_tage']} Tagen ab ({t['ablauf']})")]
    return []


@check("zertifikat_name", "Falscher Zertifikatsname", "error", "https",
       "Das Zertifikat gilt nicht für diesen Hostnamen: Browser zeigen eine Warnung.",
       "Zertifikat für alle genutzten Hostnamen (mit/ohne www.) ausstellen.")
def zertifikat_name(conn, crawl_id):
    t = fakten(conn, crawl_id).get("tls") or {}
    return [(None, t.get("fehler"))] if t and t.get("name_ok") is False else []


@check("tls_veraltet", "Veraltetes Sicherheitsprotokoll (TLS 1.0/1.1)", "error", "https",
       "Alte Protokolle sind unsicher und werden von Browsern nicht mehr unterstützt.",
       "TLS 1.0 und 1.1 auf dem Server abschalten, nur TLS 1.2/1.3 erlauben.")
def tls_veraltet(conn, crawl_id):
    t = fakten(conn, crawl_id).get("tls") or {}
    return [(None, None)] if t.get("alt_erlaubt") else []


@check("llms_fehlt", "llms.txt nicht gefunden", "notice", "ki",
       "llms.txt gibt KI-Assistenten eine kompakte Übersicht der wichtigsten Inhalte.",
       "llms.txt im Root anlegen: '# Name', Kurzbeschreibung, Links zu wichtigen Seiten.")
def llms_fehlt(conn, crawl_id):
    l = fakten(conn, crawl_id).get("llms") or {}
    return [(None, f"Status {l.get('status')}")] if l.get("status") != 200 else []


@check("llms_format", "llms.txt mit Formatfehlern", "notice", "ki",
       "Die Datei sollte Markdown sein und mit einer H1-Zeile ('# Name') beginnen.",
       "Aufbau nach llmstxt.org: H1, Zitat mit Kurzbeschreibung, Abschnitte mit Linklisten.")
def llms_format(conn, crawl_id):
    l = fakten(conn, crawl_id).get("llms") or {}
    return [(None, "beginnt nicht mit '# '")] if l.get("status") == 200 and not l.get("format_ok") else []


def _gesperrte_bots(conn, crawl_id, bots) -> list[str]:
    z = conn.execute("SELECT robots_status, robots_text, start_url FROM crawls WHERE id=?", (crawl_id,)).fetchone()
    if z[0] != 200 or not z[1]:
        return []
    robots = RobotsTxt()
    robots.parse(z[1].splitlines())
    return [bot for bot in bots if not robots.can_fetch(bot, z[2])]


@check("ki_bots_blockiert", "KI-Suchcrawler per robots.txt gesperrt", "warning", "ki",
       "Gesperrte KI-Crawler können die Website nicht als Quelle in KI-Antworten nennen.",
       "In robots.txt die gewünschten KI-Suchcrawler erlauben.")
def ki_bots_blockiert(conn, crawl_id):
    gesperrt = _gesperrte_bots(conn, crawl_id, KI_SUCH_BOTS)
    return [(None, ", ".join(gesperrt))] if gesperrt else []


@check("ki_training_bots_blockiert", "KI-Trainingscrawler per robots.txt gesperrt", "notice", "ki",
       "Zur Info, kein Fehler: Diese Crawler sammeln Texte für das Training von KI-Modellen (z. B. GPTBot, ClaudeBot). "
       "Gesperrt fließen die Inhalte nicht in künftige Modelle ein – die Marke ist dort dann weniger bekannt. "
       "Auf die Nennung als Quelle in KI-Suchen hat das keinen Einfluss.",
       "Bewusst entscheiden: Inhalte schützen (Sperre lassen) oder Bekanntheit in KI-Modellen (in robots.txt erlauben).")
def ki_training_bots_blockiert(conn, crawl_id):
    gesperrt = _gesperrte_bots(conn, crawl_id, KI_TRAINING_BOTS)
    return [(None, ", ".join(gesperrt))] if gesperrt else []


@check("llms_duenn", "llms.txt ohne Kurzbeschreibung oder Links", "notice", "ki",
       "Die llms.txt ist vorhanden, sagt KI-Assistenten aber wenig: Ohne Kurzbeschreibung ('> …') und Links "
       "auf die wichtigsten Seiten bringt sie kaum Nutzen.",
       "Unter der H1 ein Zitat mit 1–2 Sätzen zur Website, darunter H2-Abschnitte mit Linklisten '- [Titel](URL): Beschreibung'.")
def llms_duenn(conn, crawl_id):
    l = fakten(conn, crawl_id).get("llms") or {}
    if l.get("status") != 200 or not l.get("format_ok") or "links_anzahl" not in l:
        return []
    fehlt = []
    if not l.get("zusammenfassung"):
        fehlt.append("keine Kurzbeschreibung")
    if l["links_anzahl"] < LLMS_MIN_LINKS:
        fehlt.append(f"nur {l['links_anzahl']} Links")
    return [(None, ", ".join(fehlt))] if fehlt else []


@check("llms_tote_links", "llms.txt verlinkt fehlerhafte Seiten", "warning", "ki",
       "Links in der llms.txt führen auf Seiten, die beim Crawl einen Fehler lieferten. "
       "KI-Assistenten landen so auf toten Seiten.",
       "Die Links in der llms.txt korrigieren oder entfernen.")
def llms_tote_links(conn, crawl_id):
    links = (fakten(conn, crawl_id).get("llms") or {}).get("links") or []
    if not links:
        return []
    status = dict(conn.execute("SELECT url, status_code FROM seiten WHERE crawl_id=? AND blockiert=0", (crawl_id,)))
    return [(None, f"{url} ({status[url] or 'nicht erreichbar'})")
            for url in dict.fromkeys(links) if url in status and (status[url] is None or status[url] >= 400)]
