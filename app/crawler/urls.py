"""URL-Hilfen: normalisieren, intern/extern bestimmen."""

from urllib.parse import quote, urljoin, urlsplit, urlunsplit

IGNORIERTE_SCHEMATA = ("mailto:", "tel:", "javascript:", "data:", "#")
# Zeichen, die in Pfad/Query so bleiben; alles andere (z. B. Umlaute, Leerzeichen) wird %-kodiert,
# vorhandene %XX bleiben – so ist /thöne gleich /th%C3%B6ne
SICHER_PFAD = "/%:@!$&'()*+,;=-._~"
SICHER_QUERY = SICHER_PFAD + "?"


def normalisieren(href: str, basis: str) -> str | None:
    """Relativen Link auflösen, Fragment entfernen. None für Nicht-HTTP-Links."""
    href = href.strip()
    if not href or href.lower().startswith(IGNORIERTE_SCHEMATA):
        return None
    try:
        teile = urlsplit(urljoin(basis, href))
    except ValueError:
        return href  # kaputte URL bleibt erhalten, damit ein Check sie findet
    if teile.scheme not in ("http", "https"):
        return None
    pfad = quote(teile.path or "/", safe=SICHER_PFAD)
    query = quote(teile.query, safe=SICHER_QUERY)
    return urlunsplit((teile.scheme, teile.netloc.lower(), pfad, query, ""))


def host(url: str) -> str:
    try:
        return urlsplit(url).netloc.lower()
    except ValueError:
        return ""


def ist_intern(url: str, start_host: str) -> bool:
    """Gleicher Host, www. wird ignoriert."""
    def ohne_www(h: str) -> str:
        return h[4:] if h.startswith("www.") else h
    return ohne_www(host(url)) == ohne_www(start_host)
