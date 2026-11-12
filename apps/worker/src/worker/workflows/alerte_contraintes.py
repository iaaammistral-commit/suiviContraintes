"""Workflow d'alerte email des depassements de contraintes de portefeuille."""
from __future__ import annotations

import base64
import json
from typing import Literal, Optional

import pydantic
import mistralai.workflows as workflows
from mistralai.workflows import Depends
from mistralai.workflows.plugins.mistralai.connectors import (
    ToolCallClient,
    connector,
    uses_connectors,
)


drive_connector = connector("google_drive_mcp", credentials_name="test-AAM")
gmail_connector = connector("gmail", credentials_name="test-AAM-gmail")

DOSSIER_DRIVE_DEFAUT = "1O0Q7hFwKVqnkkyMZsBOfkojnC77YZao4"


class AlerteInput(pydantic.BaseModel):
    mode: Literal["dry_run", "envoi"] = "dry_run"
    destinataire: Optional[str] = None
    dossier_drive: str = DOSSIER_DRIVE_DEFAUT


@workflows.activity(name="collecter-inventaires")
async def collecter_inventaires(
    dossier_drive: str,
    drive: ToolCallClient = Depends(drive_connector),
) -> list[str]:
    """Recupere le contenu CSV des inventaires et historiques du dossier Drive."""
    textes: list[str] = []
    for mot in ("inventaire", "historique"):
        reponse = await drive.call_tool(
            tool_name="search_files",
            arguments={"query": f"title contains '{mot}'"},
        )
        fichiers = json.loads(reponse).get("files", []) if isinstance(reponse, str) else (reponse or {}).get("files", [])
        for f in fichiers:
            if f.get("file_extension") != "csv":
                continue
            telechargement = await drive.call_tool(
                tool_name="download_file_content",
                arguments={"file_id": f["id"]},
            )
            contenu = (
                json.loads(telechargement).get("content")
                if isinstance(telechargement, str) else (telechargement or {}).get("content")
            )
            if contenu:
                textes.append(base64.b64decode(contenu).decode("utf-8"))
    return textes


@workflows.activity(name="controler-contraintes")
async def controler_contraintes(textes_csv: list[str]) -> dict:
    """Controle la derniere date de chaque portefeuille et prepare l'email."""
    from worker.analyse import charger_config, construire_email, controler, parser_inventaires

    inventaires = parser_inventaires(textes_csv)
    if inventaires.empty:
        return {"date": None, "portefeuilles": {}, "sujet": None, "corps": None}
    rapport = controler(inventaires, charger_config())
    total = sum(len(v) for v in rapport["portefeuilles"].values())
    sujet, corps = (construire_email(rapport) if total else (None, None))
    return {**rapport, "sujet": sujet, "corps": corps}


@workflows.activity(name="envoyer-alerte")
async def envoyer_alerte(
    sujet: str,
    corps_html: str,
    destinataire: str,
    gmail: ToolCallClient = Depends(gmail_connector),
) -> str:
    """Envoie l'email de signalement via Gmail."""
    reponse = await gmail.call_tool(
        tool_name="send_email",
        arguments={
            "to": [destinataire],
            "subject": sujet,
            "htmlBody": corps_html,
        },
    )
    return str(reponse)


@workflows.workflow.define(
    name="alerte-contraintes",
    workflow_display_name="Alerte contraintes",
    workflow_description=(
        "Lit les inventaires sur Google Drive, controle les contraintes "
        "de la derniere date et envoie un email d'alerte en cas de depassement."
    ),
)
@uses_connectors(drive_connector, gmail_connector)
class AlerteContraintesWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, entree: AlerteInput) -> dict:
        textes = await collecter_inventaires(entree.dossier_drive)
        rapport = await controler_contraintes(textes)
        sujet = rapport.pop("sujet", None)
        corps = rapport.pop("corps", None)
        total = sum(len(v) for v in rapport["portefeuilles"].values())
        resultat = {
            "date": rapport["date"],
            "depassements": total,
            "detail": rapport["portefeuilles"],
        }
        if total == 0:
            resultat["email"] = "aucun depassement : pas d'envoi"
            return resultat
        resultat["sujet"] = sujet
        if entree.mode == "envoi":
            if not entree.destinataire:
                raise workflows.WorkflowError(
                    "Mode envoi sans destinataire : renseignez 'destinataire'."
                )
            await envoyer_alerte(sujet, corps, entree.destinataire)
            resultat["email"] = f"envoye a {entree.destinataire}"
        else:
            resultat["email"] = "dry_run : apercu seulement"
        return resultat
