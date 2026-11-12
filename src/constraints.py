"""Moteur de controle des contraintes de portefeuille."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class Contrainte:
    nom: str
    type: str
    description: str
    limite: Optional[float] = None
    valeurs_exclues: list = field(default_factory=list)


def contraintes_portefeuille(config: dict, portefeuille: str) -> list[Contrainte]:
    spec = config.get(portefeuille) or config.get("defaut") or {}
    resultats: list[Contrainte] = []
    for nom, c in spec.items():
        if not isinstance(c, dict):
            continue
        resultats.append(Contrainte(
            nom=nom,
            type=c.get("type", ""),
            description=c.get("description", ""),
            limite=c.get("limite"),
            valeurs_exclues=c.get("exclusions", []),
        ))
    return resultats


def _poids(df: pd.DataFrame) -> pd.Series:
    total = df["valeur_boursiere_EUR"].sum()
    if total <= 0:
        return pd.Series(0.0, index=df.index)
    return df["valeur_boursiere_EUR"] / total


def _evaluer_borne(nom, description, valeur, limite, sens: str, unite: str):
    if limite is None:
        return None
    if sens == "max":
        respecte = valeur <= limite
        ecart = valeur - limite
    else:
        respecte = valeur >= limite
        ecart = limite - valeur
    return {
        "contrainte": nom,
        "description": description,
        "valeur": round(valeur, 4),
        "unite": unite,
        "limite": limite,
        "sens": sens,
        "respectee": bool(respecte),
        "ecart": round(ecart, 4),
    }


def controler_inventaire(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Controle un inventaire (une date, un portefeuille) et retourne
    le detail par contrainte."""
    portefeuille = str(df["portfolio"].iloc[0])
    spec = config.get(portefeuille) or config.get("defaut") or {}
    lignes: list[dict] = []
    poids = _poids(df)

    for nom, c in spec.items():
        if not isinstance(c, dict):
            continue
        ctype = c.get("type")
        desc = c.get("description", "")
        limite = c.get("limite")

        if ctype == "poids_max_titre":
            limite_frac = limite / 100 if limite > 1 else limite
            depasse = poids[poids > limite_frac]
            poids_max = float(poids.max() if len(poids) else 0.0) * 100
            lignes.append({
                "contrainte": nom,
                "description": desc,
                "valeur": round(poids_max, 4),
                "unite": "%",
                "limite": limite,
                "sens": "max",
                "respectee": bool(depasse.empty),
                "ecart": round(poids_max - limite if len(depasse) else 0.0, 4),
                "detail": ", ".join(
                    df.loc[depasse.index, "nom_titre"].tolist()[:5]
                ),
            })
        elif ctype in ("poids_max_groupe", "poids_min_groupe"):
            colonne = c.get("colonne", "secteur_GICS")
            valeur_cible = c.get("valeur")
            total = df["valeur_boursiere_EUR"].sum() or 1.0
            if valeur_cible is None:
                poids_groupe = (df.groupby(colonne)["valeur_boursiere_EUR"].sum()
                                / total).sort_values(ascending=False)
                if ctype == "poids_max_groupe":
                    val = float(poids_groupe.iloc[0]) if len(poids_groupe) else 0.0
                    detail = str(poids_groupe.index[0]) if len(poids_groupe) else ""
                else:
                    val = float(poids_groupe.iloc[-1]) if len(poids_groupe) else 0.0
                    detail = str(poids_groupe.index[-1]) if len(poids_groupe) else ""
                sens = "max" if ctype == "poids_max_groupe" else "min"
                res = _evaluer_borne(nom, desc, val * 100, limite, sens, "%")
                res["detail"] = detail
            else:
                masque = df[colonne] == valeur_cible
                val = float(df.loc[masque, "valeur_boursiere_EUR"].sum() / total)
                sens = "max" if ctype == "poids_max_groupe" else "min"
                res = _evaluer_borne(nom, f"{desc} ({valeur_cible})", val * 100,
                                     limite, sens, "%")
                res["detail"] = str(valeur_cible)
            lignes.append(res)
        elif ctype == "exclusion_valeurs":
            colonne = c.get("colonne", "pays")
            exclues = set(c.get("exclusions", []))
            interdits = df[df[colonne].isin(exclues)]
            lignes.append({
                "contrainte": nom,
                "description": desc,
                "valeur": float(len(interdits)),
                "unite": "lignes",
                "limite": 0,
                "sens": "max",
                "respectee": interdits.empty,
                "ecart": float(len(interdits)),
                "detail": ", ".join(
                    interdits["nom_titre"].tolist()[:5]
                ) or "Aucune ligne exclue presente",
            })
        elif ctype == "nombre_max_lignes":
            lignes.append(_evaluer_borne(
                nom, desc, float(len(df)), limite, "max", "lignes"
            ))
        elif ctype == "moyenne_max_colonne":
            colonne = c.get("colonne", "emission_CO2_scope1_2_tCO2e")
            val = float(df[colonne].mean())
            lignes.append(_evaluer_borne(nom, desc, val, limite, "max", ""))
        elif ctype == "somme_max_colonne":
            colonne = c.get("colonne", "emission_CO2_scope1_2_tCO2e")
            val = float(df[colonne].sum())
            lignes.append(_evaluer_borne(nom, desc, val, limite, "max", ""))
        elif ctype == "valeur_min_portefeuille":
            val = float(df["valeur_boursiere_EUR"].sum())
            lignes.append(_evaluer_borne(nom, desc, val, limite, "min", "EUR"))

    return pd.DataFrame(lignes)


def violations_par_ligne(df: pd.DataFrame, config: dict) -> pd.Series:
    """Pour chaque ligne d'un inventaire, retourne la liste des contraintes
    violees qui impliquent cette ligne (poids individuel, exclusion, groupe
    en depassement). Les contraintes globales (nombre de lignes, valeur
    totale, moyenne/somme) ne sont pas rattachees a une ligne."""
    portefeuille = str(df["portfolio"].iloc[0])
    spec = config.get(portefeuille) or config.get("defaut") or {}
    poids = _poids(df)
    total = df["valeur_boursiere_EUR"].sum() or 1.0
    violations = pd.Series([[] for _ in range(len(df))], index=df.index)

    for nom, c in spec.items():
        if not isinstance(c, dict):
            continue
        ctype = c.get("type")
        limite = c.get("limite")

        if ctype == "poids_max_titre" and limite is not None:
            seuil = limite / 100 if limite > 1 else limite
            masque = poids > seuil
        elif ctype == "exclusion_valeurs":
            colonne = c.get("colonne", "pays")
            masque = df[colonne].isin(set(c.get("exclusions", [])))
        elif ctype in ("poids_max_groupe", "poids_min_groupe") and limite is not None:
            colonne = c.get("colonne", "secteur_GICS")
            poids_groupe = (
                df.groupby(colonne)["valeur_boursiere_EUR"].sum() / total * 100
            )
            if ctype == "poids_max_groupe":
                groupes = poids_groupe[poids_groupe > limite].index
            else:
                groupes = poids_groupe[poids_groupe < limite].index
            valeur_cible = c.get("valeur")
            if valeur_cible is not None:
                masque = pd.Series(False, index=df.index)
                if valeur_cible in groupes:
                    masque = df[colonne] == valeur_cible
            else:
                masque = df[colonne].isin(groupes)
        else:
            continue

        for idx in df.index[masque]:
            violations[idx] = violations[idx] + [nom]

    return violations


def controler_periode(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Controle chaque (date, portefeuille) du dataframe et agrege."""
    resultats: list[pd.DataFrame] = []
    for (date, portefeuille), inv in df.groupby(["date", "portfolio"]):
        detail = controler_inventaire(inv, config)
        detail["date"] = date
        detail["portfolio"] = portefeuille
        resultats.append(detail)
    if not resultats:
        return pd.DataFrame()
    out = pd.concat(resultats, ignore_index=True)
    return out
