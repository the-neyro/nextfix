"""Sicherheitsheader auch für Host-Ablehnungen und unbehandelte Serverfehler."""

from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send


class SicherheitsHeader:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        async def senden(nachricht):
            if nachricht["type"] == "http.response.start":
                headers = MutableHeaders(scope=nachricht)
                headers["X-Frame-Options"] = "DENY"
                headers["Content-Security-Policy"] = "frame-ancestors 'none'"
                headers["X-Content-Type-Options"] = "nosniff"
            await send(nachricht)
        await self.app(scope, receive, senden)


class LokaleApp(FastAPI):
    def build_middleware_stack(self) -> ASGIApp:
        # Außerhalb der Fehlerbehandlung: auch deren 500-Antwort bekommt Header.
        return SicherheitsHeader(super().build_middleware_stack())
