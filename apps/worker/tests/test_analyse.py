import pandas as pd

from worker.analyse import construire_email, controler, parser_inventaires

CONFIG = {
    "PortfolioA": {
        "poids_max_titre": {
            "type": "poids_max_titre", "description": "Poids max", "limite": 50,
        },
        "exclusion_pays": {
            "type": "exclusion_valeurs", "description": "Pays exclus",
            "colonne": "pays", "exclusions": ["Russie"],
        },
    }
}

CSV = """date,portfolio,nom_titre,code_ISIN,quantite,prix_cloture,devise,valeur_boursiere_EUR,pays,secteur_GICS,indicateur_1_20,indicateur_alphanumerique,emission_CO2_scope1_2_tCO2e
2026-01-10,PortfolioA,TitreA,FR0000000001,10,100,EUR,9000,France,Energy,5,IDX-01,2.0
2026-01-10,PortfolioA,TitreB,RU0000000002,10,100,EUR,1000,Russie,Energy,5,IDX-02,2.0
"""


def test_parser_et_controler():
    df = parser_inventaires([CSV])
    rapport = controler(df, CONFIG)
    assert rapport["date"] == "2026-01-10"
    violations = rapport["portefeuilles"]["PortfolioA"]
    titres = {v["titre"] for v in violations}
    assert "TitreA" in titres        # 90 % > 50 %
    assert "TitreB" in titres        # Russie exclue


def test_construire_email():
    rapport = {
        "date": "2026-01-10",
        "portefeuilles": {
            "PortfolioA": [
                {"titre": "TitreA", "contrainte": "poids_max_titre",
                 "valeur": 90.0, "limite": 50, "unite": "%"},
            ]
        },
    }
    sujet, html = construire_email(rapport)
    assert "1 depassement(s)" in sujet
    assert "PortfolioA" in html
    assert "TitreA" in html
    assert "<table" in html
