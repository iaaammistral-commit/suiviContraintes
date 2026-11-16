"""Envoi d'un email de signalement des depassements de contraintes."""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def config_smtp() -> dict | None:
    """Retourne la configuration SMTP depuis l'environnement, ou None."""
    hote = os.environ.get("SMTP_HOST", "")
    if not hote:
        return None
    return {
        "hote": hote,
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "utilisateur": os.environ.get("SMTP_USER", ""),
        "mot_de_passe": os.environ.get("SMTP_PASSWORD", ""),
        "expediteur": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
        "tls": os.environ.get("SMTP_TLS", "1") not in ("0", "false", "False"),
    }


def construire_message(portefeuille: str, date, violations: list[dict]) -> tuple[str, str]:
    """Construit (sujet, corps) du rapport de depassements.

    violations : liste de dicts avec nom_titre, contraintes_violees, poids.
    """
    sujet = f"[Suivi contraintes] {len(violations)} depassement(s) - {portefeuille} - {date:%Y-%m-%d}"
    lignes = [
        f"Signalement des depassements de contraintes",
        f"Portefeuille : {portefeuille}",
        f"Date : {date:%Y-%m-%d}",
        "",
        f"{len(violations)} ligne(s) concernee(s) :",
        "",
    ]
    for v in violations:
        lignes.append(
            f"- {v['nom_titre']} : {v['contraintes_violees']}"
            + (f" (poids {v['poids']:.2f} %)" if v.get("poids") is not None else "")
        )
    lignes += ["", "-- Application de suivi de contraintes"]
    corps = "\n".join(lignes)
    return sujet, corps


def envoyer_email(config: dict, destinataire: str, sujet: str, corps: str) -> None:
    """Envoie l'email via SMTP. Lever une exception en cas d'echec."""
    message = MIMEMultipart()
    message["From"] = config["expediteur"]
    message["To"] = destinataire
    message["Subject"] = sujet
    message.attach(MIMEText(corps, "plain", "utf-8"))

    with smtplib.SMTP(config["hote"], config["port"], timeout=30) as serveur:
        if config["tls"]:
            serveur.starttls()
        if config["utilisateur"]:
            serveur.login(config["utilisateur"], config["mot_de_passe"])
        serveur.send_message(message)
