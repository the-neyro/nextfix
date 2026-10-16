"""Ländernamen zu den GSC-Codes (ISO 3166 alpha-3, klein). Unbekannte Codes erscheinen groß geschrieben."""

NAMEN = {
    "deu": "Deutschland", "aut": "Österreich", "che": "Schweiz", "lie": "Liechtenstein", "lux": "Luxemburg",
    "nld": "Niederlande", "bel": "Belgien", "fra": "Frankreich", "ita": "Italien", "esp": "Spanien",
    "prt": "Portugal", "pol": "Polen", "cze": "Tschechien", "dnk": "Dänemark", "swe": "Schweden",
    "nor": "Norwegen", "fin": "Finnland", "gbr": "Vereinigtes Königreich", "irl": "Irland", "usa": "USA",
    "can": "Kanada", "aus": "Australien", "rus": "Russland", "ukr": "Ukraine", "tur": "Türkei", "ind": "Indien",
    "bra": "Brasilien", "jpn": "Japan", "chn": "China", "zzz": "unbekannt",
}


def land_name(code: str) -> str:
    return NAMEN.get(code.lower(), code.upper())
