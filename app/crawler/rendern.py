"""JavaScript ausführen: Seite in Chromium (Playwright) laden und das fertige DOM als HTML zurückgeben.

Für Websites, deren Inhalt erst per JavaScript entsteht (React, Vue, Angular …). Google rendert solche Seiten,
viele andere Crawler (u. a. die der KI-Suchdienste) nicht. Bilder, Schriften und Videos werden nicht geladen:
Für Text und Links braucht es sie nicht, und der Server wird weniger belastet.
"""

AUSLASSEN = {"image", "media", "font"}


class Renderer:
    """Ein Chromium für viele Seiten. Benutzung: with Renderer(user_agent) as r: html = r.rendern(url)."""

    def __init__(self, user_agent: str, timeout_s: int = 20, ruhe_ms: int = 3000):
        self.user_agent, self.timeout_ms, self.ruhe_ms = user_agent, timeout_s * 1000, ruhe_ms

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._kontext = self._browser.new_context(user_agent=self.user_agent)
        self._kontext.route("**/*", lambda route: route.abort() if route.request.resource_type in AUSLASSEN
                            else route.continue_())
        return self

    def __exit__(self, *_):
        self._kontext.close()
        self._browser.close()
        self._pw.stop()

    def rendern(self, url: str) -> str | None:
        """HTML nach Ausführung von JavaScript, None bei Fehler (dann gilt das Roh-HTML)."""
        seite = self._kontext.new_page()
        try:
            seite.goto(url, wait_until="load", timeout=self.timeout_ms)
            try:
                seite.wait_for_load_state("networkidle", timeout=self.ruhe_ms)
            except Exception:
                pass  # Dauer-Anfragen (Chat, Tracking): Stand nach der Wartezeit nehmen
            return seite.content()
        except Exception:
            return None
        finally:
            seite.close()
