"""Envoi d'emails via Gmail API (OAuth2) — fonctionne sur tous les réseaux (HTTPS:443)."""
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

from app.config import settings


def _get_gmail_service():
    """Construit le service Gmail API à partir des credentials .env."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not settings.gmail_client_id or not settings.gmail_client_secret or not settings.gmail_refresh_token:
        raise ValueError(
            "GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET et GMAIL_REFRESH_TOKEN "
            "doivent être configurés dans .env (lance scripts/gmail_auth.py)"
        )

    creds = Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    return build("gmail", "v1", credentials=creds)


def send_candidature_email(
    to_email: str,
    subject: str,
    lm_texte: str,
    cv_path: str | None = None,
) -> None:
    """
    Envoie la candidature via Gmail API.
    Lève ValueError si la config est absente.
    Lève googleapiclient.errors.HttpError en cas d'erreur API.
    """
    service = _get_gmail_service()

    msg = MIMEMultipart()
    msg["From"] = settings.smtp_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(lm_texte or "(Aucune lettre de motivation rédigée)", "plain", "utf-8"))

    if cv_path:
        cv_file = Path(cv_path)
        if cv_file.exists():
            with cv_file.open("rb") as f:
                part = MIMEApplication(f.read(), Name=cv_file.name)
            part["Content-Disposition"] = f'attachment; filename="{cv_file.name}"'
            msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
