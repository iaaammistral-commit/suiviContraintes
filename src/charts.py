"""Graphiques de suivi du controle des contraintes."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def graphique_conformite(resultats: pd.DataFrame) -> go.Figure:
    """Taux de contraintes respectees par date et portefeuille."""
    if resultats.empty:
        return go.Figure()
    agrege = (
        resultats.groupby(["date", "portfolio"])["respectee"]
        .mean()
        .reset_index()
    )
    agrege["taux"] = agrege["respectee"] * 100
    fig = go.Figure()
    for portefeuille, groupe in agrege.groupby("portfolio"):
        groupe = groupe.sort_values("date")
        fig.add_trace(go.Scatter(
            x=groupe["date"],
            y=groupe["taux"],
            mode="lines+markers",
            name=portefeuille,
            hovertemplate="%{x|%Y-%m-%d} : %{y:.1f}%% respectees<extra>%{fullData.name}</extra>",
        ))
    fig.update_layout(
        title="Taux de contraintes respectees",
        yaxis_title="% contraintes respectees",
        yaxis_range=[0, 105],
        legend_title="Portefeuille",
        hovermode="x unified",
    )
    return fig


def graphique_violations_par_contrainte(resultats: pd.DataFrame) -> go.Figure:
    """Nombre de violations par contrainte sur la periode."""
    if resultats.empty:
        return go.Figure()
    violations = resultats[~resultats["respectee"]]
    compte = (
        violations.groupby(["portfolio", "contrainte"])
        .size()
        .reset_index(name="violations")
    )
    fig = go.Figure()
    for portefeuille, groupe in compte.groupby("portfolio"):
        groupe = groupe.sort_values("violations", ascending=True)
        fig.add_trace(go.Bar(
            y=groupe["contrainte"],
            x=groupe["violations"],
            orientation="h",
            name=portefeuille,
        ))
    fig.update_layout(
        title="Violations par contrainte sur la periode",
        xaxis_title="Nombre de dates en violation",
        barmode="group",
    )
    return fig


def graphique_valeurs_contrainte(resultats: pd.DataFrame, contrainte: str) -> go.Figure:
    """Evolution de la valeur d'une contrainte et de sa limite."""
    sous = resultats[resultats["contrainte"] == contrainte].sort_values("date")
    if sous.empty:
        return go.Figure()
    fig = make_subplots(specs=[[{"secondary_y": False}]])
    for portefeuille, groupe in sous.groupby("portfolio"):
        fig.add_trace(go.Scatter(
            x=groupe["date"], y=groupe["valeur"], mode="lines+markers",
            name=f"{portefeuille} - valeur",
        ))
        limite = groupe["limite"].iloc[0]
        fig.add_trace(go.Scatter(
            x=groupe["date"], y=[limite] * len(groupe),
            mode="lines", line=dict(dash="dash"),
            name=f"{portefeuille} - limite",
        ))
    fig.update_layout(
        title=f"Evolution de la contrainte : {contrainte}",
        hovermode="x unified",
    )
    return fig
