"""
Script one-time pour autoriser l'accès Gmail API et obtenir le refresh_token.

Usage :
  python scripts/gmail_auth.py

Prérequis :
  pip install google-auth-oauthlib google-api-python-client
  Fichier config/gmail_credentials.json téléchargé depuis Google Cloud Console.

Résultat :
  Affiche GMAIL_REFRESH_TOKEN à copier dans .env
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "gmail_credentials.json"


def main():
    if not CREDENTIALS_FILE.exists():
        print(f"[ERREUR] Fichier introuvable : {CREDENTIALS_FILE}")
        print("Télécharge les credentials OAuth2 depuis console.cloud.google.com")
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    flow.redirect_uri = "http://localhost:8080/"
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")

    print("\nOuvre ce lien dans ton navigateur :")
    print(auth_url)
    print("\nEn attente du callback sur http://localhost:8080 ...")

    creds = flow.run_local_server(port=8080, open_browser=False)

    info = json.loads(creds.to_json())
    print("\n=== Copie ces valeurs dans ton .env ===\n")
    print(f"GMAIL_CLIENT_ID={info['client_id']}")
    print(f"GMAIL_CLIENT_SECRET={info['client_secret']}")
    print(f"GMAIL_REFRESH_TOKEN={info['refresh_token']}")
    print("\n=======================================")


if __name__ == "__main__":
    main()
