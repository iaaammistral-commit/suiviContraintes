# Suivi de contraintes de portefeuille

Application Streamlit qui lit des inventaires de portefeuille (CSV sur Google
Drive ou dossier local), affiche les inventaires, liste les contraintes de
chaque portefeuille, les controle et presente le resultat dans des graphiques
sur une periode choisie.

## Fonctionnalites

- **Inventaires** : consultation par portefeuille et par date.
- **Contraintes** : liste des contraintes definies par portefeuille
  (`config/constraints.yaml`).
- **Controle** : evaluation des contraintes sur une periode selectionnable,
  avec :
  - taux de contraintes respectees par date et portefeuille,
  - nombre de violations par contrainte sur la periode,
  - evolution de la valeur d'une contrainte face a sa limite,
  - tableau detaille a la derniere date.

## Format attendu des fichiers (CSV)

Colonnes : `date, portfolio, nom_titre, code_ISIN, quantite, prix_cloture,
devise, valeur_boursiere_EUR, pays, secteur_GICS, indicateur_1_20,
indicateur_alphanumerique, emission_CO2_scope1_2_tCO2e`

Les anciennes orthographes `indicateur_alphanterique` et
`emission_CO2_scope1_2_tCO2` restent acceptees a la lecture.

## Installation

```bash
pip install -r requirements.txt
python scripts/generate_sample_data.py   # donnees d'exemple (optionnel)
streamlit run app.py
```

## Sources de donnees

1. **Dossier local** (par defaut `data/sample/`) : tous les CSV sont charges
   recursivement.
2. **Google Drive** : renseignez l'ID du dossier Drive dans la barre laterale
   et definissez la variable d'environnement :

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/chemin/vers/compte-service.json
```

Le compte de service doit avoir un acces lecteur au dossier Drive partage.
Vous pouvez aussi importer directement des fichiers CSV via la barre laterale.

## Contraintes supportees (`config/constraints.yaml`)

| Type | Parametres | Description |
|---|---|---|
| `poids_max_titre` | `limite` (%) | Poids max d'une ligne |
| `poids_max_groupe` | `colonne`, `valeur` (option), `limite` (%) | Poids max d'un groupe |
| `poids_min_groupe` | `colonne`, `valeur` (option), `limite` (%) | Poids min d'un groupe |
| `exclusion_valeurs` | `colonne`, `exclusions` | Valeurs interdites |
| `nombre_max_lignes` | `limite` | Nombre max de lignes |
| `moyenne_max_colonne` | `colonne`, `limite` | Moyenne max d'une colonne |
| `somme_max_colonne` | `colonne`, `limite` | Somme max d'une colonne |
| `valeur_min_portefeuille` | `limite` (EUR) | Valeur totale minimale |

Les contraintes sont definies par portefeuille ; la cle `defaut` s'applique
aux portefeuilles sans configuration.

## Signalement par email

Dans l'onglet Inventaires, si des lignes sont en violation, un bouton
« Envoyer l'email de signalement » envoie le detail des depassements de la
date affichee pour le portefeuille selectionne. Configuration SMTP via
variables d'environnement :

```bash
export SMTP_HOST=smtp.exemple.fr
export SMTP_PORT=587
export SMTP_USER=expediteur@exemple.fr
export SMTP_PASSWORD=********
export SMTP_FROM=expediteur@exemple.fr   # optionnel (defaut : SMTP_USER)
export SMTP_TO=destinataire@exemple.fr   # optionnel (pre-remplit le champ)
```

Sans configuration SMTP, un apercu du message est affiche a la place de
l'envoi. Le port 465 (SSL implicite) n'est pas supporte : utilisez le port
587 avec TLS (defaut).

## Tests

```bash
pytest
```
