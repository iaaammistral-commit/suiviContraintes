import io

import pandas as pd
import pytest
import yaml

from src.constraints import (
    controler_inventaire,
    controler_periode,
    violations_par_ligne,
)
from src.loader import charger_csv_texte

CONFIG = """
PortfolioA:
  poids_max_titre:
    type: poids_max_titre
    description: Poids max d'un titre
    limite: 50
  exclusion_pays:
    type: exclusion_valeurs
    description: Pays exclus
    colonne: pays
    exclusions: ["Russie"]
"""

CSV = """date,portfolio,nom_titre,code_ISIN,quantite,prix_cloture,devise,valeur_boursiere_EUR,pays,secteur_GICS,indicateur_1_20,indicateur_alphanumerique,emission_CO2_scope1_2_tCO2e
2026-01-10,PortfolioA,TitreA,FR0000000001,10,100,EUR,1000,France,Energy,5,IDX-01,2.0
2026-01-10,PortfolioA,TitreB,RU0000000002,10,100,EUR,1000,Russie,Energy,5,IDX-02,2.0
2026-01-11,PortfolioA,TitreA,FR0000000001,10,100,EUR,1000,France,Energy,5,IDX-01,2.0
2026-01-11,PortfolioA,TitreB,RU0000000002,10,100,EUR,1000,France,Energy,5,IDX-02,2.0
"""


@pytest.fixture
def config():
    return yaml.safe_load(CONFIG)


def test_chargement_schema():
    df = charger_csv_texte(CSV)
    assert len(df) == 4
    assert df["date"].dtype.kind == "M"
    assert df["valeur_boursiere_EUR"].sum() == 4000


def test_alias_ancienne_orthographe():
    csv_ancien = (
        CSV.replace("indicateur_alphanumerique", "indicateur_alphanterique")
        .replace("emission_CO2_scope1_2_tCO2e", "emission_CO2_scope1_2_tCO2")
    )
    df = charger_csv_texte(csv_ancien)
    assert "indicateur_alphanumerique" in df.columns
    assert "emission_CO2_scope1_2_tCO2e" in df.columns
    assert len(df) == 4


def test_exclusion_pays_violee(config):
    df = charger_csv_texte(CSV)
    inventaire = df[(df["date"] == pd.Timestamp("2026-01-10"))]
    detail = controler_inventaire(inventaire, config)
    exclusion = detail[detail["contrainte"] == "exclusion_pays"].iloc[0]
    assert not exclusion["respectee"]
    assert exclusion["detail"] == "TitreB"


def test_exclusion_pays_respectee(config):
    df = charger_csv_texte(CSV)
    inventaire = df[(df["date"] == pd.Timestamp("2026-01-11"))]
    detail = controler_inventaire(inventaire, config)
    exclusion = detail[detail["contrainte"] == "exclusion_pays"].iloc[0]
    assert exclusion["respectee"]


def test_poids_max_titre(config):
    df = charger_csv_texte(CSV)
    inventaire = df[(df["date"] == pd.Timestamp("2026-01-10"))]
    detail = controler_inventaire(inventaire, config)
    poids = detail[detail["contrainte"] == "poids_max_titre"].iloc[0]
    assert poids["respectee"]
    assert abs(poids["valeur"] - 50.0) < 0.01


def test_violations_par_ligne(config):
    df = charger_csv_texte(CSV)
    inventaire = df[(df["date"] == pd.Timestamp("2026-01-10"))]
    violations = violations_par_ligne(inventaire, config)
    titre_b = inventaire.index[inventaire["nom_titre"] == "TitreB"][0]
    assert violations[titre_b] == ["exclusion_pays"]
    titre_a = inventaire.index[inventaire["nom_titre"] == "TitreA"][0]
    assert violations[titre_a] == []


def test_violations_par_ligne_poids(config):
    df = charger_csv_texte(CSV)
    inventaire = df[(df["date"] == pd.Timestamp("2026-01-11"))].copy()
    inventaire.loc[inventaire["nom_titre"] == "TitreA", "valeur_boursiere_EUR"] = 9000.0
    violations = violations_par_ligne(inventaire, config)
    titre_a = inventaire.index[inventaire["nom_titre"] == "TitreA"][0]
    assert violations[titre_a] == ["poids_max_titre"]


def test_controle_periode(config):
    df = charger_csv_texte(CSV)
    resultats = controler_periode(df, config)
    assert set(resultats["portfolio"]) == {"PortfolioA"}
    assert len(resultats) == 4  # 2 dates x 2 contraintes
    par_date = resultats.groupby("date")["respectee"].mean()
    assert par_date[pd.Timestamp("2026-01-10")] == 0.5
    assert par_date[pd.Timestamp("2026-01-11")] == 1.0
