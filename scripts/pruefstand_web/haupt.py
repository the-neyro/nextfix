"""Hauptwebsite des Prüfstands: alle Fälle auf Seitenebene plus robots.txt, Sitemap und llms.txt mit Fehlern."""

from scripts.pruefstand_web import (ORGANISATION, Website, haupt_crawl, haupt_dateien, haupt_hreflang, haupt_inhalt,
                                    haupt_ki, haupt_links, haupt_technik, png, sitemap)


def bauen(w: Website) -> Website:
    for teil in (haupt_crawl, haupt_inhalt, haupt_technik, haupt_links, haupt_ki, haupt_hreflang, haupt_dateien):
        teil.alles(w)
    w.datei("/bilder/ok.png", png(8, 8), "image/png")
    w.seite("/doppelt-in-sitemap")
    w.seite("/verwaist", im_menue=False)   # nur in der Sitemap, nirgends verlinkt
    w.hubs(start_kopf=ORGANISATION, start_nein=["ki_ohne_entitaet", "sitemap_falsche_seiten", "orphan_sitemap",
                                                         "meta_refresh", "unkomprimiert"])

    w.datei("/robots.txt", (
        "User-agent: *\nDisallow: /gesperrt/\nDisalow: /tippfehler/\nKaputte Zeile\n\n"
        "User-agent: OAI-SearchBot\nDisallow: /\n\nUser-agent: GPTBot\nDisallow: /\n\n"
        f"Sitemap: {w.basis}sitemap.xml\n"), "text/plain; charset=utf-8")
    w.erwarte(ja=["robots_formatfehler", "robots_unbekannte_felder", "ki_bots_blockiert", "ki_training_bots_blockiert"],
              nein=["robots_fehlt", "sitemap_fehlt", "sitemap_nicht_in_robots", "sitemap_formatfehler", "llms_fehlt",
                    "llms_format"])

    w.datei("/sitemap.xml", sitemap(w, [
        "/", "/uebersicht", "/fehlt-404", "/weiterleitung-301", "/kopie-canonical", "/noindex-meta",
        "/x-robots-noindex", "/x-robots-noarchive", "/doppelt-in-sitemap", "/doppelt-in-sitemap",
        "/sitemap-nie-verlinkt-404", "/verwaist"]), "application/xml")
    for pfad in ("/fehlt-404", "/weiterleitung-301", "/kopie-canonical", "/noindex-meta", "/x-robots-noindex",
                 "/doppelt-in-sitemap"):
        w.erwarte(pfad, ja=["sitemap_falsche_seiten"])
    w.erwarte("/x-robots-noarchive", nein=["sitemap_falsche_seiten"])
    w.erwarte(ja=[("sitemap_falsche_seiten", "/sitemap-nie-verlinkt-404"), ("orphan_sitemap", "/verwaist")])
    w.erwarte("/uebersicht", nein=["orphan_sitemap"])

    # llms.txt ohne Kurzbeschreibung (dünn) und mit toten Links
    w.datei("/llms.txt", (
        f"# Prüfstand Hauptseite\n\n## Seiten\n- [Start]({w.basis})\n- [Übersicht]({w.basis}uebersicht)\n"
        f"- [Alte Preise]({w.basis}fehlt-404)\n- [Nie verlinkt]({w.basis}llms-nie-verlinkt-404)\n"
        f"- [Umzug]({w.basis}weiterleitung-301)\n"), "text/plain; charset=utf-8")
    w.erwarte(ja=["llms_duenn", ("llms_tote_links", "/fehlt-404")], nein=[("llms_tote_links", "/weiterleitung-301")])
    w.erwarte(ja=[("llms_tote_links", "/llms-nie-verlinkt-404")],
              warum={"llms_tote_links": "auch nicht verlinkte Ziele der llms.txt müssen geprüft werden"})
    return w
