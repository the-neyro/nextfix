"""URL-Filter aus den Projekteinstellungen: nur bestimmte Pfade crawlen, Pfade sperren, Parameter entfernen.

Masken gelten für Pfad + Query (z. B. "/blog/", "/shop/*/details", "*?sort="), wie in robots.txt
als Präfix: "/blog" passt auf "/blog", "/blog/" und "/blogger". "*" steht für beliebige Zeichen,
"$" am Ende für "genau hier zu Ende".
"""

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def liste(text: str | None) -> list[str]:
    """Eingabe aus einem Textfeld: ein Eintrag pro Zeile (oder durch Komma getrennt)."""
    return [t.strip() for t in re.split(r"[\n,]", text or "") if t.strip()]


def _muster(maske: str) -> re.Pattern:
    ende = maske.endswith("$")
    kern = re.escape(maske.rstrip("$")).replace(r"\*", ".*")
    if not kern.startswith(("/", ".*")):
        kern = ".*" + kern   # "?sort=" oder "tag" darf irgendwo vorkommen
    return re.compile(kern + ("$" if ende else ""))


@dataclass
class UrlFilter:
    erlauben: list[str] = field(default_factory=list)
    sperren: list[str] = field(default_factory=list)
    parameter: list[str] = field(default_factory=list)   # "*" = alle Parameter entfernen

    def __post_init__(self):
        self._erlauben = [_muster(m) for m in self.erlauben]
        self._sperren = [_muster(m) for m in self.sperren]
        self._parameter = {p.lower() for p in self.parameter}

    def erlaubt(self, url: str) -> bool:
        teile = urlsplit(url)
        pfad = (teile.path or "/") + (f"?{teile.query}" if teile.query else "")
        if self._erlauben and not any(m.match(pfad) for m in self._erlauben):
            return False
        return not any(m.match(pfad) for m in self._sperren)

    def bereinigen(self, url: str) -> str:
        if not self._parameter:
            return url
        teile = urlsplit(url)
        if not teile.query:
            return url
        rest = [] if "*" in self._parameter else [
            (k, v) for k, v in parse_qsl(teile.query, keep_blank_values=True) if k.lower() not in self._parameter]
        return urlunsplit(teile._replace(query=urlencode(rest)))
