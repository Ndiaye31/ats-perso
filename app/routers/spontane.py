import csv
import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.scraper_ft import main as scraper_ft_main
from app.find_emails import main as find_emails_main
from app.send_candidatures import main as send_candidatures_main
from app.email_sender import send_candidature_email
from app.ai.generate_lm import generate_lm
from app.profil import load_profil

router = APIRouter(prefix="/spontane", tags=["spontane"])
logger = logging.getLogger(__name__)

# Chemins absolus — mêmes que dans scraper_ft.py / find_emails.py / send_candidatures.py
BASE_DIR      = Path(__file__).resolve().parent.parent.parent
CONTACTS_FILE = str(BASE_DIR / "contacts.csv")
LOG_FILE      = str(BASE_DIR / "envois.json")

PROFIL_LABELS = {
    "data": "Data Analyste",
    "powerbi": "Consultant Power BI",
    "sharepoint": "Administrateur SharePoint Online",
}


# ─── Pipeline étapes ───────────────────────────────────────────

@router.post("/scrape-ft")
def scrape_ft() -> dict:
    """Scrape les offres France Travail et génère entreprises.csv."""
    try:
        result = scraper_ft_main()
        return result or {"entreprises": 0}
    except Exception as e:
        logger.error("scrape_ft failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/find-emails")
def find_emails() -> dict:
    """Cherche les emails RH via Hunter.io depuis entreprises.csv."""
    try:
        result = find_emails_main()
        return result or {"trouves": 0, "ignores": 0}
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail="entreprises.csv introuvable — lancez d'abord /spontane/scrape-ft",
        )
    except Exception as e:
        logger.error("find_emails failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send")
def send_candidatures() -> dict:
    """Envoie les candidatures spontanées depuis contacts.csv via Gmail OAuth2."""
    try:
        result = send_candidatures_main()
        return result or {"envoyes": 0, "ignores": 0, "erreurs": 0}
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail="contacts.csv introuvable — lancez d'abord /spontane/find-emails",
        )
    except Exception as e:
        logger.error("send_candidatures failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Contacts ──────────────────────────────────────────────────

@router.get("/contacts")
def get_contacts() -> list[dict]:
    """Retourne la liste des contacts depuis contacts.csv."""
    if not Path(CONTACTS_FILE).exists():
        return []

    log = {}
    if Path(LOG_FILE).exists():
        with open(LOG_FILE, "r") as f:
            log = json.load(f)

    contacts = []
    with open(CONTACTS_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            contacts.append({
                "prenom":     row.get("prenom", ""),
                "nom":        row.get("nom", ""),
                "email":      row.get("email", ""),
                "entreprise": row.get("entreprise", ""),
                "profil":     row.get("profil", ""),
                "lieu":       row.get("lieu", ""),
                "envoye":     row.get("email", "") in log,
            })
    return contacts


# ─── Génération LM spontanée ────────────────────────────────────

class GenerateLMRequest(BaseModel):
    prenom: str
    entreprise: str
    profil: str  # data / powerbi / sharepoint
    lieu: str = ""


@router.post("/generate-lm")
def generate_lm_spontane(req: GenerateLMRequest) -> dict:
    """Génère une LM personnalisée pour une candidature spontanée."""
    try:
        profil_data = load_profil()
        titre = PROFIL_LABELS.get(req.profil, req.profil)
        description = (
            f"Candidature spontanée pour un poste de {titre} "
            f"chez {req.entreprise}"
            + (f" ({req.lieu})" if req.lieu else "") + "."
        )
        lm_texte = generate_lm(
            title=titre,
            company=req.entreprise,
            description=description,
            profil=profil_data,
        )
        return {"lm_texte": lm_texte}
    except Exception as e:
        logger.error("generate_lm_spontane failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Envoi unitaire ─────────────────────────────────────────────

class SendOneRequest(BaseModel):
    prenom: str
    nom: str
    email: str
    entreprise: str
    profil: str
    lm_texte: str


@router.post("/send-one")
def send_one(req: SendOneRequest) -> dict:
    """Envoie un email de candidature spontanée à un contact unique."""
    titre = PROFIL_LABELS.get(req.profil, req.profil)
    subject = f"Candidature spontanée – {titre}"
    try:
        send_candidature_email(
            to_email=req.email,
            subject=subject,
            lm_texte=req.lm_texte,
        )
        # Log l'envoi
        log = {}
        if Path(LOG_FILE).exists():
            with open(LOG_FILE, "r") as f:
                log = json.load(f)
        from datetime import datetime
        log[req.email] = {
            "prenom": req.prenom,
            "entreprise": req.entreprise,
            "profil": req.profil,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        with open(LOG_FILE, "w") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
        return {"success": True, "message": f"Email envoyé à {req.email}"}
    except Exception as e:
        logger.error("send_one failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
