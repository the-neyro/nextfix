"""Automatisch gefundene Links dürfen keine privaten Netze ansprechen."""

import socket

import httpx
import pytest

from app.crawler import crawler, urls
from app.crawler.crawler import CrawlEinstellungen, Crawler
from app.core import projekte
from app.db import verbinden


@pytest.mark.parametrize("adresse", ["192.168.178.1", "10.0.0.1", "172.16.0.1", "127.0.0.2",
    "169.254.169.254", "0.0.0.0", "[::1]", "[fe80::1]", "[fc00::1]", "[::ffff:192.168.1.1]"])
def test_private_ip_adressen_sind_lokal(adresse):
    assert urls.ist_lokal(f"http://{adresse}/")


def test_dns_prueft_alle_adressen_und_meldet_tote_domains(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::1", 0, 0, 0))])
    assert urls.ist_lokal("https://router.example/")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))])
    assert not urls.ist_lokal("https://public.example/")
    def fehlt(*a, **k):
        raise socket.gaierror("Test: kein DNS")
    monkeypatch.setattr(socket, "getaddrinfo", fehlt)
    assert not urls.ist_lokal("https://fehlt.example/")


def test_externer_link_auf_tote_domain_wird_als_defekt_gespeichert(monkeypatch):
    def fehlt(*a, **k):
        raise socket.gaierror("Test: kein DNS")
    monkeypatch.setattr(socket, "getaddrinfo", fehlt)
    def antwort(r):
        raise httpx.ConnectError("Test: kein DNS", request=r)
    conn = verbinden()
    p = projekte.anlegen(conn, "example.de")
    cid = conn.execute("INSERT INTO crawls (projekt_id,start_url) VALUES (?,?)",
                       (p.id, "https://example.de/")).lastrowid
    sid = conn.execute("INSERT INTO seiten (crawl_id,url,tiefe) VALUES (?,?,0)",
                       (cid, "https://example.de/")).lastrowid
    conn.execute("INSERT INTO links (crawl_id,seite_id,ziel_url,art,intern) VALUES (?,?,?,?,0)",
                 (cid, sid, "https://abgelaufen.example/", "a"))
    conn.commit()
    c = Crawler(conn, cid, CrawlEinstellungen(start_url="https://example.de/", crawl_delay=0),
                httpx.Client(transport=httpx.MockTransport(antwort)))
    monkeypatch.setattr(crawler, "EXTERN_PAUSE", 0)
    monkeypatch.setattr(crawler.time, "sleep", lambda s: None)
    c._extern_pruefen()
    zeile = conn.execute("SELECT status_code FROM ressourcen WHERE crawl_id=? AND url=?",
                         (cid, "https://abgelaufen.example/")).fetchone()
    assert zeile is not None and zeile[0] is None


def test_private_links_und_metaziele_werden_nie_abgerufen(monkeypatch):
    anfragen = []
    def antwort(r):
        anfragen.append(str(r.url))
        return httpx.Response(200)
    conn = verbinden()
    p = projekte.anlegen(conn, "example.de")
    cid = conn.execute("INSERT INTO crawls (projekt_id,start_url) VALUES (?,?)",
                       (p.id, "https://example.de/")).lastrowid
    sid = conn.execute("INSERT INTO seiten (crawl_id,url,canonical,hreflang,tiefe) VALUES (?,?,?,?,0)",
        (cid, "https://example.de/", "http://192.168.178.1/canonical",
         '[{"url":"http://10.0.0.1/sprache"}]')).lastrowid
    conn.execute("INSERT INTO links (crawl_id,seite_id,ziel_url,art,intern) VALUES (?,?,?,?,0)",
                 (cid, sid, "http://169.254.169.254/", "a"))
    conn.execute("UPDATE crawls SET fakten=? WHERE id=?",
                 ('{"llms":{"links":["http://172.16.0.1/llms"]}}', cid))
    conn.commit()
    c = Crawler(conn, cid, CrawlEinstellungen(start_url="https://example.de/", crawl_delay=0),
                httpx.Client(transport=httpx.MockTransport(antwort)))
    monkeypatch.setattr(crawler, "EXTERN_PAUSE", 0)
    c._extern_pruefen()
    c._ziele_pruefen()
    assert anfragen == []


@pytest.mark.parametrize("methode", ["HEAD", "GET"])
def test_externe_redirects_auf_private_ziele_werden_gestoppt(monkeypatch, methode):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))])
    anfragen = []
    def antwort(r):
        anfragen.append((r.method, str(r.url)))
        if r.url.host == "public.example":
            if methode == "GET" and r.method == "HEAD":
                return httpx.Response(405)
            return httpx.Response(302, headers={"Location": "http://192.168.178.1/"})
        return httpx.Response(200)
    client = httpx.Client(transport=httpx.MockTransport(antwort), follow_redirects=True)
    try:
        crawler._extern_status(client, "https://public.example/")
    except httpx.HTTPError:
        pass
    assert anfragen and all("192.168" not in url for _, url in anfragen)


def test_eigene_lokale_startseite_bleibt_erlaubt(testseite):
    from app.core import audit
    conn = verbinden()
    p = projekte.anlegen(conn, "127.0.0.1")
    audit.einstellungen_setzen(conn, p.id, start_url=testseite, crawl_delay=0)
    crawl = audit.crawl_starten(conn, p.id, warten=True)
    assert crawl["status"] == "fertig"
    assert audit.seiten_liste(conn, crawl["id"])
