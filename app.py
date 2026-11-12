"""Application Streamlit de suivi des contraintes de portefeuille."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from src.charts import (
    graphique_conformite,
    graphique_valeurs_contrainte,
    graphique_violations_par_contrainte,
)
from src.constraints import controler_periode, contraintes_portefeuille
from src.loader import charger_dossier, charger_drive

RACINE = Path(__file__).resolve().parent
DOSSIER_EXEMPLE = RACINE / "data" / "sample"
FICHIER_CONFIG = RACINE / "config" / "constraints.yaml"


@st.cache_data(show_spinner=False)
def _charger_config() -> dict:
    with open(FICHIER_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@st.cache_data(show_spinner="Chargement des inventaires...")
def _charger_donnees(source: str, dossier_id: str, dossier_local: str) -> pd.DataFrame:
    if source == "Google Drive":
        return charger_drive(dossier_id)
    return charger_dossier(dossier_local)


def page_inventaires(df: pd.DataFrame) -> None:
    st.header("Inventaires")
    portefeuilles = sorted(df["portfolio"].unique())
    portefeuille = st.selectbox("Portefeuille", portefeuilles)
    dates = sorted(df[df["portfolio"] == portefeuille]["date"].unique())
    date = st.selectbox("Date", dates, index=len(dates) - 1)
    inventaire = df[(df["portfolio"] == portefeuille) & (df["date"] == date)]
    st.metric("Lignes", len(inventaire))
    st.metric("Valeur totale (EUR)", f"{inventaire['valeur_boursiere_EUR'].sum():,.2f}")
    st.dataframe(inventaire.drop(columns=["date", "portfolio"]), width="stretch")


def page_contraintes(config: dict, portefeuilles: list[str]) -> None:
    st.header("Contraintes par portefeuille")
    for portefeuille in portefeuilles:
        with st.expander(f"{portefeuille}", expanded=(portefeuille == portefeuilles[0])):
            contraintes = contraintes_portefeuille(config, portefeuille)
            if not contraintes:
                st.info("Aucune contrainte definie pour ce portefeuille.")
                continue
            st.table(pd.DataFrame([
                {
                    "Nom": c.nom,
                    "Type": c.type,
                    "Description": c.description,
                    "Limite": str(c.limite) if c.limite is not None else "-",
                    "Exclusions": ", ".join(map(str, c.valeurs_exclues)) or "-",
                }
                for c in contraintes
            ]))


def page_controle(df: pd.DataFrame, config: dict) -> None:
    st.header("Controle des contraintes")
    col1, col2 = st.columns(2)
    with col1:
        debut, fin = st.date_input(
            "Periode d'analyse",
            value=(df["date"].min().date(), df["date"].max().date()),
            min_value=df["date"].min().date(),
            max_value=df["date"].max().date(),
        )
    with col2:
        portefeuilles_choisis = st.multiselect(
            "Portefeuilles", sorted(df["portfolio"].unique()),
            default=sorted(df["portfolio"].unique()),
        )
    if isinstance(debut, tuple):
        debut, fin = debut

    filtre = df[
        (df["date"] >= pd.Timestamp(debut))
        & (df["date"] <= pd.Timestamp(fin))
        & (df["portfolio"].isin(portefeuilles_choisis))
    ]
    if filtre.empty:
        st.warning("Aucune donnee sur la periode selectionnee.")
        return

    resultats = controler_periode(filtre, config)
    st.subheader("Evolution de la conformite")
    st.plotly_chart(graphique_conformite(resultats), width="stretch")

    st.subheader("Violations par contrainte")
    st.plotly_chart(
        graphique_violations_par_contrainte(resultats), width="stretch"
    )

    contraintes_dispos = sorted(resultats["contrainte"].unique())
    contrainte_choisie = st.selectbox(
        "Detail d'une contrainte", contraintes_dispos
    )
    st.plotly_chart(
        graphique_valeurs_contrainte(resultats, contrainte_choisie),
        width="stretch",
    )

    st.subheader("Detail du controle")
    latest = resultats["date"].max()
    st.caption(f"Resultats de la derniere date de la periode : {latest:%Y-%m-%d}")
    detail = resultats[resultats["date"] == latest].drop(columns=["date"])
    detail["statut"] = detail["respectee"].map({True: "OK", False: "VIOLATION"})
    st.dataframe(detail, width="stretch")


def main() -> None:
    st.set_page_config(page_title="Suivi de contraintes", layout="wide")
    st.title("Suivi de contraintes de portefeuille")

    with st.sidebar:
        st.subheader("Source des donnees")
        source = st.radio(
            "Source", ["Dossier local", "Google Drive"],
            help="Drive requiert GOOGLE_APPLICATION_CREDENTIALS (compte de service).",
        )
        dossier_local = st.text_input("Dossier local", str(DOSSIER_EXEMPLE))
        dossier_id = st.text_input(
            "ID du dossier Drive", "1O0Q7hFwKVqnkkyMZsBOfkojnC77YZao4"
        )
        fichiers_upload = st.file_uploader(
            "Ou importer des fichiers CSV",
            type=["csv"], accept_multiple_files=True,
        )

    config = _charger_config()

    try:
        if fichiers_upload:
            from src.loader import charger_csv_texte
            frames = [charger_csv_texte(f.getvalue().decode("utf-8"))
                      for f in fichiers_upload]
            df = pd.concat(frames, ignore_index=True)
        else:
            df = _charger_donnees(source, dossier_id, dossier_local)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Impossible de charger les donnees : {exc}")
        return

    st.sidebar.success(
        f"{len(df)} lignes, {df['date'].nunique()} dates, "
        f"{df['portfolio'].nunique()} portefeuilles"
    )

    onglet = st.tabs(["Inventaires", "Contraintes", "Controle"])
    with onglet[0]:
        page_inventaires(df)
    with onglet[1]:
        page_contraintes(config, sorted(df["portfolio"].unique()))
    with onglet[2]:
        page_controle(df, config)


if __name__ == "__main__":
    main()
