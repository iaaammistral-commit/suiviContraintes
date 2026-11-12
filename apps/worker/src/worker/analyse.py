"""Analyse des inventaires et controle des contraintes (fonctions pures)."""
from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd
import yaml

COLONNES = [
    "date", "portfolio", "nom_titre", "code_ISIN", "quantite",
    "prix_cloture", "devise", "valeur_boursiere_EUR", "pays",
    "secteur_GICS", "indicateur_1_20", "indicateur_alphanumerique",
    "emission_CO2_scope1_2_tCO2e",
]

ALIAS = {
    "indicateur_alphanterique": "indicateur_alphanumerique",
    "emission_CO2_scope1_2_tCO2": "emission_CO2_scope1_2_tCO2e",
}


def charger_config() -> dict:
    chemin = os.environ.get("CONTRAINTES_CONFIG")
    if chemin and Path(chemin).exists():
        with open(chemin, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    for base in [Path.cwd(), *Path.cwd().parents]:
        candidat = base / "config" / "constraints.yaml"
        if candidat.exists():
            with open(candidat, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    raise FileNotFoundError(
        "config/constraints.yaml introuvable (definissez CONTRAINTES_CONFIG)"
    )


def parser_inventaires(textes_csv: list[str]) -> pd.DataFrame:
    frames = []
    for texte in textes_csv:
        df = pd.read_csv(io.StringIO(texte))
        df.columns = [ALIAS.get(c.strip(), c.strip()) for c in df.columns]
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for c in ["quantite", "prix_cloture", "valeur_boursiere_EUR",
                  "indicateur_1_20", "emission_CO2_scope1_2_tCO2e"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        frames.append(df.dropna(subset=["date"]))
    if not frames:
        return pd.DataFrame(columns=COLONNES)
    return pd.concat(frames, ignore_index=True)


def _violations_inventaire(inv: pd.DataFrame, spec: dict) -> list[dict]:
    violations: list[dict] = []
    total = inv["valeur_boursiere_EUR"].sum() or 1.0
    poids = inv["valeur_boursiere_EUR"] / total

    for nom, c in spec.items():
        if not isinstance(c, dict):
            continue
        ctype = c.get("type")
        limite = c.get("limite")

        if ctype == "poids_max_titre" and limite is not None:
            seuil = limite / 100 if limite > 1 else limite
            for i, p in poids.items():
                if p > seuil:
                    violations.append({
                        "titre": inv.loc[i, "nom_titre"],
                        "contrainte": nom,
                        "valeur": round(float(p) * 100, 2),
                        "limite": limite, "unite": "%",
                    })
        elif ctype == "exclusion_valeurs":
            colonne = c.get("colonne", "pays")
            for i, row in inv.iterrows():
                if row[colonne] in set(c.get("exclusions", [])):
                    violations.append({
                        "titre": row["nom_titre"],
                        "contrainte": nom,
                        "valeur": str(row[colonne]),
                        "limite": "exclu", "unite": "",
                    })
        elif ctype in ("poids_max_groupe", "poids_min_groupe") and limite is not None:
            colonne = c.get("colonne", "secteur_GICS")
            poids_groupe = inv.groupby(colonne)["valeur_boursiere_EUR"].sum() / total * 100
            en_violation = (
                poids_groupe[poids_groupe > limite]
                if ctype == "poids_max_groupe"
                else poids_groupe[poids_groupe < limite]
            )
            for groupe, val in en_violation.items():
                violations.append({
                    "titre": f"{colonne} = {groupe}",
                    "contrainte": nom,
                    "valeur": round(float(val), 2),
                    "limite": limite, "unite": "%",
                })
        elif ctype == "nombre_max_lignes" and limite is not None and len(inv) > limite:
            violations.append({
                "titre": "(portefeuille)", "contrainte": nom,
                "valeur": float(len(inv)), "limite": limite, "unite": "lignes",
            })
        elif ctype == "moyenne_max_colonne" and limite is not None:
            colonne = c.get("colonne", "emission_CO2_scope1_2_tCO2e")
            val = float(inv[colonne].mean())
            if val > limite:
                violations.append({
                    "titre": "(portefeuille)", "contrainte": nom,
                    "valeur": round(val, 2), "limite": limite, "unite": "",
                })
        elif ctype == "valeur_min_portefeuille" and limite is not None:
            val = float(inv["valeur_boursiere_EUR"].sum())
            if val < limite:
                violations.append({
                    "titre": "(portefeuille)", "contrainte": nom,
                    "valeur": round(val, 2), "limite": limite, "unite": "EUR",
                })
    return violations


def controler(df: pd.DataFrame, config: dict) -> dict:
    """Controle la derniere date passee ou du jour de chaque portefeuille."""
    aujourdhui = pd.Timestamp.now().normalize()
    df = df[df["date"] <= aujourdhui]
    if df.empty:
        return {"date": None, "portefeuilles": {}}
    date = df["date"].max()
    rapport: dict = {"date": date.strftime("%Y-%m-%d"), "portefeuilles": {}}
    for portefeuille, inv in df[df["date"] == date].groupby("portfolio"):
        spec = config.get(portefeuille) or config.get("defaut") or {}
        inv = inv.reset_index(drop=True)
        rapport["portefeuilles"][portefeuille] = _violations_inventaire(inv, spec)
    return rapport


def construire_email(rapport: dict) -> tuple[str, str]:
    """Construit (sujet, corps_html) du rapport de depassements."""
    total = sum(len(v) for v in rapport["portefeuilles"].values())
    sujet = f"[Suivi contraintes] {total} depassement(s) au {rapport['date']}"
    lignes = [
        "<html><body style='font-family: Arial, sans-serif;'>",
        f"<h2>Depassements de contraintes - {rapport['date']}</h2>",
        f"<p>{total} depassement(s) detecte(s).</p>",
    ]
    for portefeuille, violations in rapport["portefeuilles"].items():
        if not violations:
            continue
        lignes.append(f"<h3>{portefeuille} ({len(violations)})</h3>")
        lignes.append(
            "<table border='1' cellpadding='6' cellspacing='0' "
            "style='border-collapse: collapse;'>"
            "<tr style='background-color: #ffcccc;'><th>Titre</th>"
            "<th>Contrainte</th><th>Valeur</th><th>Limite</th></tr>"
        )
        for v in violations:
            lignes.append(
                f"<tr><td>{v['titre']}</td><td>{v['contrainte']}</td>"
                f"<td>{v['valeur']}{v['unite']}</td><td>{v['limite']}{v['unite']}</td></tr>"
            )
        lignes.append("</table>")
    lignes.append(
        "<p style='color: #888; font-size: 12px;'>Genere automatiquement "
        "par le workflow Mistral 'alerte-contraintes'.</p></body></html>"
    )
    return sujet, "\n".join(lignes)
