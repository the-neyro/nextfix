"""URL-Hilfen: normalisieren, intern/extern bestimmen."""

from urllib.parse import quote, urljoin, urlsplit, urlunsplit

STANDARD_PORTS = {"http": "80", "https": "443"}

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
    return urlunsplit((teile.scheme, _netloc(teile.netloc, teile.scheme), pfad, query, ""))


def _netloc(netloc: str, schema: str) -> str:
    """Host einheitlich schreiben: klein, Umlaut-Domains als Punycode (bäcker.de = xn--bcker-gra.de),
    ohne Standard-Port (:443 bei https, :80 bei http)."""
    netloc = netloc.lower()
    name, _, port = netloc.rpartition(":") if ":" in netloc and not netloc.endswith("]") else (netloc, "", "")
    if port == STANDARD_PORTS.get(schema):
        netloc = name
    try:
        return netloc.encode("idna").decode("ascii")
    except UnicodeError:
        return netloc


def host(url: str) -> str:
    try:
        teile = urlsplit(url)
    except ValueError:
        return ""
    return _netloc(teile.netloc, teile.scheme)


def ist_intern(url: str, start_host: str) -> bool:
    """Gleicher Host, www. wird ignoriert."""
    def ohne_www(h: str) -> str:
        return h[4:] if h.startswith("www.") else h
    return ohne_www(host(url)) == ohne_www(_netloc(start_host, ""))
