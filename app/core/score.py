"""Website-Zustand (Health), eigene Formel – Fassung 2 vom 16.10.2026.

Pro Check c mit Treffern und Gewicht w:
    strafe = w * (SOCKEL + (1 - SOCKEL) * anteil)      anteil = betroffene Seiten / geprüfte Seiten (ganze Site = 1)
    Health = 100 * exp(-Σ strafe / K)

Warum so (Fassung 1 war 100 * (1 - Σ strafe / Σ w) über alle Checks): Die meisten der ~100 Checks schlagen nie an
(hreflang, TLS …). Sie blähten Σ w auf, echte Probleme „verdünnten“ sich – schwache Websites bekamen 92–99.
Jetzt zählt nur, was gefunden wurde; der Anteil betroffener Seiten wiegt stark (SOCKEL klein), und e^(-x) hält
den Wert zwischen 0 und 100.

Fassung 3 vom 18.10.2026: „Wenig Text“ wiegt nicht mehr wie ein Fehler, sondern wie eine Warnung. Google wertet die
Länge eines Textes allein nicht (SEO Starter Guide); das Sondergewicht 3 hatte technisch saubere Websites auf ~60 gedrückt.
"""

import math

GEWICHTE = {"error": 3.0, "warning": 1.0, "notice": 0.0}
GEWICHT_CHECK: dict[str, float] = {}   # Abweichungen vom Schweregrad (zurzeit keine)
SOCKEL = 0.15
K = 8.0   # je größer, desto milder: Σ strafe = K → Health 37


def gewicht(schwere: str, check_id: str | None = None) -> float:
    return GEWICHT_CHECK.get(check_id, GEWICHTE[schwere]) if check_id else GEWICHTE[schwere]


def strafe(schwere: str, betroffen: int, ganze_site: bool, seiten_gesamt: int, check_id: str | None = None) -> float:
    """Abzug eines Checks (0 ohne Treffer)."""
    if betroffen == 0 and not ganze_site:
        return 0.0
    anteil = 1.0 if ganze_site else min(1.0, betroffen / max(seiten_gesamt, 1))
    return gewicht(schwere, check_id) * (SOCKEL + (1 - SOCKEL) * anteil)


def aus_abzug(abzug: float) -> float:
    return round(100 * math.exp(-abzug / K), 1)


def berechnen(checks: list[tuple], seiten_gesamt: int) -> float | None:
    """checks: (schwere, betroffene_seiten, betrifft_ganze_site[, check_id[, bezug]]) je durchgeführtem Check.

    bezug: eigene Bezugsgröße statt seiten_gesamt (z. B. gemessene Seiten bei der Ladezeit-Stichprobe).
    Gibt None zurück, wenn keine gewichteten Checks dabei sind.
    """
    if not any(gewicht(c[0], c[3] if len(c) > 3 else None) for c in checks):
        return None
    return aus_abzug(sum(strafe(*c[:3], (c[4] if len(c) > 4 and c[4] else seiten_gesamt), c[3] if len(c) > 3 else None)
                         for c in checks))
