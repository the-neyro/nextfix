"""Antworten und gzip-Inhalte begrenzt lesen, auch wenn Größenangaben fehlen."""

import zlib

import httpx


class AntwortZuGross(httpx.HTTPError):
    def __init__(self, max_bytes: int):
        super().__init__(f"Antwort zu groß (höchstens {max_bytes} Bytes)")


def _entpacken(inhalt: bytes, max_bytes: int) -> bytes:
    entpacker = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        daten = entpacker.decompress(inhalt, max_bytes + 1)
    except zlib.error as fehler:
        raise httpx.DecodingError(f"gzip: {fehler}") from None
    if len(daten) > max_bytes or entpacker.unconsumed_tail:
        raise AntwortZuGross(max_bytes)
    if not entpacker.eof or entpacker.unused_data:
        raise httpx.DecodingError("gzip: unvollständige Datei oder zusätzliche Daten")
    return daten


def _inhalt(antwort: httpx.Response, max_bytes: int) -> bytes:
    # Vorab geladene Antworten kommen z. B. aus MockTransport.
    if antwort.is_stream_consumed:
        if len(antwort.content) > max_bytes:
            raise AntwortZuGross(max_bytes)
        return antwort.content
    kodierung = antwort.headers.get("content-encoding", "identity").lower().strip()
    if kodierung not in ("identity", "", "gzip", "deflate"):
        raise httpx.DecodingError(f"Nicht unterstützte Content-Encoding: {kodierung}")
    entpacker = (zlib.decompressobj(16 + zlib.MAX_WBITS) if kodierung == "gzip" else
                 zlib.decompressobj() if kodierung == "deflate" else None)
    daten = bytearray()
    roh_bytes = 0
    for stueck in antwort.iter_raw():
        roh_bytes += len(stueck)
        if roh_bytes > max_bytes:
            raise AntwortZuGross(max_bytes)
        if entpacker:
            try:
                stueck = entpacker.decompress(stueck, max_bytes - len(daten) + 1)
            except zlib.error as fehler:
                raise httpx.DecodingError(str(fehler)) from None
        if len(daten) + len(stueck) > max_bytes:
            raise AntwortZuGross(max_bytes)
        daten.extend(stueck)
    if entpacker and (not entpacker.eof or entpacker.unused_data):
        raise httpx.DecodingError("Unvollständige komprimierte Antwort oder zusätzliche Daten")
    return bytes(daten)


def _lesen(client: httpx.Client, url: str, max_bytes: int, folgen: bool = True) -> httpx.Response:
    """GET mit Grenze für übertragene und entpackte Bytes; Redirect-Bodies nie laden."""
    geschichte = []
    for _ in range(client.max_redirects + 1):
        with client.stream("GET", url, follow_redirects=False, headers={"Accept-Encoding": "identity"}) as r:
            if folgen and r.has_redirect_location:
                geschichte.append(r)
                url = str(r.next_request.url)
                continue
            inhalt = _inhalt(r, max_bytes)
            antwort = httpx.Response(r.status_code, content=inhalt, request=r.request, history=geschichte)
            # Der Inhalt ist bereits entpackt; Header erst danach für Text-Encoding/Metadaten übernehmen.
            antwort.headers.update(r.headers)
            return antwort
    raise httpx.TooManyRedirects("Zu viele Weiterleitungen")
