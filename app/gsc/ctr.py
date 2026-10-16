"""Erwartete Klickrate je Position (eigene Kurve, grob nach öffentlichen CTR-Studien).

Wird für die Sichtbarkeit und die Mock-Daten genutzt. Keine Google-Zahl.
"""

# Position 1–10 einzeln, danach Stufen
_TOP10 = [0.28, 0.15, 0.11, 0.08, 0.065, 0.05, 0.04, 0.032, 0.027, 0.024]


def erwartete_ctr(position: float) -> float:
    if position < 1:
        position = 1
    if position <= 10:
        return _TOP10[round(position) - 1]
    if position <= 20:
        return 0.01
    if position <= 30:
        return 0.003
    return 0.0
