"""Core Web Vitals im Labor messen: echtes Chromium (Playwright), Werte wie Lighthouse.

Gemessen: LCP, CLS, TBT (Ersatz für INP, das ohne Nutzer-Interaktion nicht messbar ist), FCP, TTFB,
übertragene Bytes, Anzahl Anfragen. Jede Messung in frischem Browser-Kontext (kalter Cache).

Mobil wie Lighthouse: kleines Display, 4× langsamere CPU, Netz „Slow 4G“. Wir drosseln wirklich (DevTools) und
nehmen dafür Lighthouses eigene Korrektur für echtes Drosseln (RTT × 3,75, Durchsatz × 0,9): 562,5 ms / 1,44 Mbit/s.
Lighthouse rechnet die Drosselung meist nur hoch („simulated“); Werte sind vergleichbar, nicht identisch.
Abgleich mit echten Lighthouse-Werten (10 Seiten, mobil + Desktop): LCP-Abweichung meist unter 10 %.
Abgleich 16.10.2026 mit PageSpeed Insights (Startseite einer echten Website, mobil): PSI 99 / LCP 1,8 s / TBT 0 ms,
wir 96 / 2,2 s / 29 ms – CPU ×4 passt also auch auf schnellen Macs; höhere Faktoren (×12: 83) wären zu streng.
Ein Lighthouse-Lauf eines Drittanbieters (85, TBT 574 ms) war ein Ausreißer seiner Infrastruktur.
Ohne Speed Index.
"""

import math
from dataclasses import asdict, dataclass

GERAETE = {
    "mobile": {
        "kontext": {"viewport": {"width": 412, "height": 823}, "device_scale_factor": 1.75, "is_mobile": True,
                    "has_touch": True,
                    "user_agent": "Mozilla/5.0 (Linux; Android 11; moto g power (2022)) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36 SeoToolBot/0.1"},
        "netz": {"latency": 150 * 3.75, "downloadThroughput": 1638.4 * 0.9 * 1024 / 8,
                 "uploadThroughput": 675 * 0.9 * 1024 / 8},
        "cpu": 4,
    },
    "desktop": {
        "kontext": {"viewport": {"width": 1350, "height": 940}, "device_scale_factor": 1,
                    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 SeoToolBot/0.1"},
        # Desktop ohne Korrektur: im Abgleich mit Lighthouse-Werten (LCP 386–422 ms) am genauesten
        "netz": {"latency": 40, "downloadThroughput": 10240 * 1024 / 8, "uploadThroughput": 10240 * 1024 / 8},
        "cpu": 1,
    },
}

# Lighthouse-10-Bewertungskurven (p10 = Wert für Score 0,9; median = Score 0,5) und Gewichte ohne Speed Index
KURVEN = {
    "mobile": {"fcp": (1800, 3000), "lcp": (2500, 4000), "tbt": (200, 600), "cls": (0.1, 0.25)},
    "desktop": {"fcp": (934, 1600), "lcp": (1200, 2400), "tbt": (150, 350), "cls": (0.1, 0.25)},
}
GEWICHTE = {"fcp": 0.10, "lcp": 0.25, "tbt": 0.30, "cls": 0.25}  # Summe 0,9 → wird normiert

# Google-Schwellen (gut / schlecht) für die Ampel
SCHWELLEN = {"lcp": (2500, 4000), "cls": (0.1, 0.25), "tbt": (200, 600), "fcp": (1800, 3000), "ttfb": (800, 1800)}

BEOBACHTER_JS = """
window.__cwv = {lcp: 0, cls: 0, lange: []};
try {
  new PerformanceObserver(l => { for (const e of l.getEntries()) window.__cwv.lcp = e.startTime; })
    .observe({type: 'largest-contentful-paint', buffered: true});
  let sitzung = 0, eintraege = [];
  new PerformanceObserver(l => {
    for (const e of l.getEntries()) {
      if (e.hadRecentInput) continue;
      const erster = eintraege[0], letzter = eintraege[eintraege.length - 1];
      if (sitzung && e.startTime - letzter.startTime < 1000 && e.startTime - erster.startTime < 5000) {
        sitzung += e.value; eintraege.push(e);
      } else { sitzung = e.value; eintraege = [e]; }
      window.__cwv.cls = Math.max(window.__cwv.cls, sitzung);
    }
  }).observe({type: 'layout-shift', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) window.__cwv.lange.push([e.startTime, e.duration]); })
    .observe({type: 'longtask', buffered: true});
} catch (e) {}
"""

AUSWERTEN_JS = """() => {
  const nav = performance.getEntriesByType('navigation')[0];
  const fcp = performance.getEntriesByName('first-contentful-paint')[0];
  const f = fcp ? fcp.startTime : 0;
  const tbt = window.__cwv.lange.filter(([s, d]) => s >= f).reduce((sum, [s, d]) => sum + Math.max(0, d - 50), 0);
  return {ttfb: nav ? nav.responseStart : null, fcp: fcp ? fcp.startTime : null,
          lcp: window.__cwv.lcp || null, cls: window.__cwv.cls, tbt: tbt};
}"""


@dataclass
class Messung:
    url: str
    geraet: str
    ttfb: float | None = None
    fcp: float | None = None
    lcp: float | None = None
    cls: float | None = None
    tbt: float | None = None
    bytes: int = 0
    anfragen: int = 0
    score: int | None = None
    fehler: str | None = None

    def als_dict(self) -> dict:
        return asdict(self)


def lognormal_score(wert: float, p10: float, median: float) -> float:
    """Lighthouse-Formel: Anteil, der „schlechter“ ist, auf einer Log-Normal-Kurve."""
    if wert <= 0:
        return 1.0
    standard = math.log(wert / median) * 0.9062727 / -math.log(p10 / median)
    return max(0.0, min(1.0, (1 - math.erf(standard)) / 2))


def score(m: dict, geraet: str) -> int | None:
    """Performance-Score 0–100 (ohne Speed Index, Gewichte normiert)."""
    teile = [(GEWICHTE[k], lognormal_score(m[k], *KURVEN[geraet][k])) for k in GEWICHTE if m.get(k) is not None]
    if len(teile) < len(GEWICHTE):
        return None
    return round(100 * sum(g * s for g, s in teile) / sum(g for g, _ in teile))


def bewertung(metrik: str, wert: float | None) -> str | None:
    if wert is None or metrik not in SCHWELLEN:
        return None
    gut, schlecht = SCHWELLEN[metrik]
    return "gut" if wert <= gut else "mittel" if wert <= schlecht else "schlecht"


class Messer:
    """Ein Chromium für viele Messungen. Benutzung: with Messer() as m: m.messen(url, "mobile")."""

    def __init__(self, drosseln: bool = True, timeout_s: int = 45, nachlauf_ms: int = 2500):
        self.drosseln, self.timeout_ms, self.nachlauf_ms = drosseln, timeout_s * 1000, nachlauf_ms

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        return self

    def __exit__(self, *_):
        self._browser.close()
        self._pw.stop()

    def messen(self, url: str, geraet: str = "mobile") -> Messung:
        g = GERAETE[geraet]
        m = Messung(url, geraet)
        kontext = self._browser.new_context(**g["kontext"])
        try:
            seite = kontext.new_page()
            seite.add_init_script(BEOBACHTER_JS)
            cdp = kontext.new_cdp_session(seite)
            cdp.send("Network.enable")
            gezaehlt = {"bytes": 0, "anfragen": 0}

            def fertig(e):
                gezaehlt["bytes"] += int(e.get("encodedDataLength") or 0)
                gezaehlt["anfragen"] += 1
            cdp.on("Network.loadingFinished", fertig)
            if self.drosseln:
                cdp.send("Network.emulateNetworkConditions", {"offline": False, **g["netz"]})
                cdp.send("Emulation.setCPUThrottlingRate", {"rate": g["cpu"]})
            antwort = seite.goto(url, wait_until="load", timeout=self.timeout_ms)
            if antwort is not None and antwort.status >= 400:
                m.fehler = f"HTTP {antwort.status}"
            try:
                seite.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass  # Seiten mit Dauer-Anfragen (Chat-Widgets, Tracking) werden nie ganz ruhig
            seite.wait_for_timeout(self.nachlauf_ms)
            werte = seite.evaluate(AUSWERTEN_JS)
            for k in ("ttfb", "fcp", "lcp", "tbt"):
                if werte.get(k) is not None:
                    setattr(m, k, round(werte[k]))
            m.cls = round(werte.get("cls") or 0, 3)
            m.bytes, m.anfragen = gezaehlt["bytes"], gezaehlt["anfragen"]
            m.score = score(asdict(m), geraet)
        except Exception as e:
            m.fehler = f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"
        finally:
            kontext.close()
        return m
