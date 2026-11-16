import pandas as pd
import pytest

from src.emailing import construire_message


def test_construire_message():
    violations = [
        {"nom_titre": "LVMH", "contraintes_violees": "poids_max_titre", "poids": 12.5},
        {"nom_titre": "Shell", "contraintes_violees": "poids_max_titre, co2_moyen_max", "poids": None},
    ]
    sujet, corps = construire_message("PortfolioA", pd.Timestamp("2026-11-12"), violations)
    assert "2 depassement(s)" in sujet
    assert "PortfolioA" in sujet
    assert "2026-11-12" in sujet
    assert "LVMH" in corps
    assert "poids 12.50 %" in corps
    assert "Shell" in corps
    assert "poids_max_titre, co2_moyen_max" in corps


def test_construire_message_sans_poids():
    violations = [{"nom_titre": "X", "contraintes_violees": "exclusion_pays", "poids": None}]
    sujet, corps = construire_message("PortfolioB", pd.Timestamp("2026-01-10"), violations)
    assert sujet == "[Suivi contraintes] 1 depassement(s) - PortfolioB - 2026-01-10"
    assert "poids %" not in corps
