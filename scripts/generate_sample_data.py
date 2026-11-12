"""Genere des donnees d'exemple avec le meme schema que les fichiers Drive.

Usage : python scripts/generate_sample_data.py
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "data" / "sample"

TITRES = [
    ("LVMH", "FR00000121014", "France", "Consumer Discretionary", 712.0, 2.1),
    ("ASML Holding", "NL0010273215", "Pays-Bas", "Information Technology", 845.0, 0.3),
    ("SAP SE", "DE0007164600", "Allemagne", "Information Technology", 228.0, 0.1),
    ("Nestle SA", "CH0038863350", "Suisse", "Consumer Staples", 82.0, 1.8),
    ("Novartis AG", "CH0012005267", "Suisse", "Health Care", 98.0, 0.8),
    ("TotalEnergies SE", "FR0000120271", "France", "Energy", 58.0, 13.0),
    ("Sanofi", "FR0000120578", "France", "Health Care", 92.0, 1.5),
    ("Allianz SE", "DE0008404005", "Allemagne", "Financials", 342.0, 0.2),
    ("Siemens AG", "DE0005557508", "Allemagne", "Industrials", 218.0, 1.3),
    ("Airbus SE", "FR00000125190", "France", "Industrials", 168.0, 0.7),
    ("BNP Paribas", "FR0000131104", "France", "Financials", 68.0, 0.1),
    ("Schneider Electric SE", "FR0000121972", "France", "Industrials", 238.0, 2.9),
    ("Iberdrola SA", "ES014458018", "Espagne", "Utilities", 14.0, 5.2),
    ("Enel SpA", "IT0003128367", "Italie", "Utilities", 7.0, 10.1),
    ("Relx PLC", "GB00B2TQHZ95", "Royaume-Uni", "Industrials", 32.0, 0.2),
    ("Novo Nordisk A/S", "DK0060534915", "Danemark", "Health Care", 26.0, 0.8),
    ("ING Groep NV", "NL0011821202", "Pays-Bas", "Financials", 19.0, 0.5),
    ("Zurich Insurance Group AG", "CH0011075394", "Suisse", "Financials", 548.0, 0.5),
    ("ABB Ltd", "CH0012142147", "Suisse", "Industrials", 142.0, 0.3),
    ("Linde PLC", "IE00Z12S8B50", "Irlande", "Materials", 448.0, 6.9),
    ("Equinor ASA", "NO0010081235", "Norvege", "Energy", 26.0, 7.2),
    ("Vinci SA", "FR0000125486", "France", "Industrials", 118.0, 1.2),
]

PORTEFEUILLES = {
    "PortfolioA": (35, 70.0),
    "PortfolioB": (40, 400.0),
    "PortfolioC": (25, 1200.0),
}


def _indicateur(i: int) -> str:
    return f"IDX-{i % 20:02d}{chr(65 + i % 26)}"


def generer() -> None:
    random.seed(42)
    SORTIE.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range(end=pd.Timestamp.now().normalize(), periods=24, freq="15D")
    lignes = []
    for portefeuille, (n_lignes, facteur) in PORTEFEUILLES.items():
        for i, (nom, isin, pays, secteur, prix, co2) in enumerate(TITRES[:n_lignes]):
            quantite = max(1, int(1000 / (i + 3) * facteur / 100))
            for date in dates:
                variation = 1 + random.uniform(-0.03, 0.03)
                prix_j = round(prix * variation, 2)
                lignes.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "portfolio": portefeuille,
                    "nom_titre": nom,
                    "code_ISIN": isin,
                    "quantite": quantite,
                    "prix_cloture": prix_j,
                    "devise": "EUR",
                    "valeur_boursiere_EUR": round(quantite * prix_j, 2),
                    "pays": pays,
                    "secteur_GICS": secteur,
                    "indicateur_1_20": (i % 20) + 1,
                    "indicateur_alphanumerique": _indicateur(i),
                    "emission_CO2_scope1_2_tCO2e": co2,
                })
    df = pd.DataFrame(lignes)
    df.to_csv(SORTIE / "historique_exemple.csv", index=False)
    print(f"{len(df)} lignes ecrites dans {SORTIE / 'historique_exemple.csv'}")


if __name__ == "__main__":
    generer()
