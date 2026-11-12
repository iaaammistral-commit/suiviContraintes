"""Chargement des inventaires depuis Google Drive ou un dossier local."""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional

import pandas as pd

COLONNES = [
    "date",
    "portfolio",
    "nom_titre",
    "code_ISIN",
    "quantite",
    "prix_cloture",
    "devise",
    "valeur_boursiere_EUR",
    "pays",
    "secteur_GICS",
    "indicateur_1_20",
    "indicateur_alphanumerique",
    "emission_CO2_scope1_2_tCO2e",
]

ALIAS_COLONNES = {
    "indicateur_alphanterique": "indicateur_alphanumerique",
    "emission_CO2_scope1_2_tCO2": "emission_CO2_scope1_2_tCO2e",
}


def _nettoie(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [ALIAS_COLONNES.get(c.strip(), c.strip()) for c in df.columns]
    manquantes = [c for c in COLONNES if c not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans le fichier: {manquantes}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["quantite", "prix_cloture", "valeur_boursiere_EUR",
              "indicateur_1_20", "emission_CO2_scope1_2_tCO2e"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date"])
    df["portfolio"] = df["portfolio"].astype(str).str.strip()
    return df[COLONNES]


def charger_csv_texte(texte: str) -> pd.DataFrame:
    return _nettoie(pd.read_csv(io.StringIO(texte)))


def charger_fichier(chemin: str | Path) -> pd.DataFrame:
    chemin = Path(chemin)
    if chemin.suffix.lower() in (".xls", ".xlsx"):
        return _nettoie(pd.read_excel(chemin))
    return _nettoie(pd.read_csv(chemin))


def charger_dossier(dossier: str | Path) -> pd.DataFrame:
    dossier = Path(dossier)
    fichiers = sorted(
        p for p in dossier.rglob("*")
        if p.suffix.lower() in (".csv", ".xls", ".xlsx")
    )
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier CSV/Excel trouve dans {dossier}")
    frames = [charger_fichier(p) for p in fichiers]
    return pd.concat(frames, ignore_index=True)


def _client_drive():
    from googleapiclient.discovery import build
    from google.oauth2 import service_account

    fichier_sa = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not fichier_sa or not Path(fichier_sa).exists():
        raise RuntimeError(
            "Definissez GOOGLE_APPLICATION_CREDENTIALS vers un fichier "
            "de compte de service Google (JSON) pour acceder a Drive."
        )
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_file(
        fichier_sa, scopes=scopes
    )
    return build("drive", "v3", credentials=creds)


def charger_drive(dossier_id: str) -> pd.DataFrame:
    """Telecharge tous les CSV d'un dossier Drive (recursif)."""
    service = _client_drive()
    frames: list[pd.DataFrame] = []
    page_token: Optional[str] = None
    while True:
        resp = service.files().list(
            q=f"'{dossier_id}' in parents and mimeType='text/csv' and trashed=false",
            fields="nextPageToken, files(id, name)",
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            data = service.files().get_media(fileId=f["id"]).execute()
            frames.append(charger_csv_texte(data.decode("utf-8")))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    if not frames:
        raise FileNotFoundError(f"Aucun CSV trouve dans le dossier Drive {dossier_id}")
    return pd.concat(frames, ignore_index=True)
