"""
Router candidatures spontanées — mairies & éducation.
Pipeline : scrape → generate-lm → send
"""
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cible_spontanee import CibleSpontanee
from app.scrapers.mairies import scrape_mairies
from app.scrapers.education import scrape_education
from app.ai.lm_spontane import generate_lm_spontane
from app.email_sender import send_candidature_email

router = APIRouter(prefix="/spontane", tags=["spontane"])
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# CV par secteur (déjà présents dans config/)
CV_PAR_SECTEUR: dict[str, str] = {
    "mairies":   str(BASE_DIR / "config" / "cv_mairies.pdf"),
    "education": str(BASE_DIR / "config" / "cv_education.pdf"),
}

SECTEURS_VALIDES = {"mairies", "education"}


# ─── Scraping ──────────────────────────────────────────────────────────────────

@router.post("/scrape")
def scrape(
    secteur: Optional[str] = Query(None, description="mairies | education (défaut: les deux)"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Lance le scraping des mairies et/ou établissements scolaires.
    Insère les nouvelles cibles en base (pas de doublon sur nom+secteur).
    """
    if secteur and secteur not in SECTEURS_VALIDES:
        raise HTTPException(status_code=400, detail=f"secteur doit être parmi {SECTEURS_VALIDES}")

    resultats: list[dict] = []

    if secteur in (None, "mairies"):
        try:
            resultats.extend(scrape_mairies())
        except Exception as e:
            logger.error("scrape mairies failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Erreur scraping mairies: {e}")

    if secteur in (None, "education"):
        try:
            resultats.extend(scrape_education())
        except Exception as e:
            logger.error("scrape education failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Erreur scraping éducation: {e}")

    inseres = 0
    ignores = 0

    for item in resultats:
        # Déduplication sur (nom, secteur)
        existant = db.scalar(
            select(CibleSpontanee).where(
                CibleSpontanee.nom == item["nom"],
                CibleSpontanee.secteur == item["secteur"],
            )
        )
        if existant:
            ignores += 1
            continue

        date_scrape = None
        if item.get("date_scrape"):
            try:
                date_scrape = datetime.fromisoformat(item["date_scrape"])
            except ValueError:
                date_scrape = datetime.now()

        cv_path = CV_PAR_SECTEUR.get(item["secteur"], "")

        cible = CibleSpontanee(
            nom=item["nom"],
            secteur=item["secteur"],
            type_organisation=item.get("type_organisation"),
            departement=item.get("departement"),
            education_type=item.get("education_type"),
            email=item.get("email") or None,
            description=item.get("description"),
            titre_poste=item.get("titre_poste"),
            cv_path=cv_path if Path(cv_path).exists() else None,
            statut="neuf",
            date_scrape=date_scrape or datetime.now(),
        )
        db.add(cible)
        inseres += 1

    db.commit()
    logger.info("scrape spontane: %d insérées, %d doublons ignorés", inseres, ignores)
    return {"inseres": inseres, "ignores": ignores, "total": inseres + ignores}


# ─── Consultation ──────────────────────────────────────────────────────────────

@router.get("/cibles")
def list_cibles(
    secteur: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    avec_email_seulement: bool = Query(False),
    limit: int = Query(100, le=2500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """Liste les cibles (filtrable par secteur, statut, présence d'email). Retourne items + total."""
    base = select(CibleSpontanee)
    if secteur:
        base = base.where(CibleSpontanee.secteur == secteur)
    if statut:
        base = base.where(CibleSpontanee.statut == statut)
    if avec_email_seulement:
        base = base.where(CibleSpontanee.email.isnot(None))

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    cibles = db.scalars(base.order_by(CibleSpontanee.created_at.desc()).limit(limit).offset(offset)).all()
    return {"items": [_to_dict(c) for c in cibles], "total": total, "limit": limit, "offset": offset}


@router.get("/cibles/{cible_id}")
def get_cible(cible_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    cible = db.get(CibleSpontanee, cible_id)
    if not cible:
        raise HTTPException(status_code=404, detail="Cible introuvable")
    return _to_dict(cible)


# ─── PATCH LM ──────────────────────────────────────────────────────────────────

class PatchLMRequest(BaseModel):
    lm_texte: str


@router.patch("/cibles/{cible_id}/lm")
def patch_lm(cible_id: uuid.UUID, body: PatchLMRequest, db: Session = Depends(get_db)) -> dict:
    """Sauvegarde une LM éditée manuellement et passe la cible à 'prêt'."""
    cible = db.get(CibleSpontanee, cible_id)
    if not cible:
        raise HTTPException(status_code=404, detail="Cible introuvable")
    cible.lm_texte = body.lm_texte
    cible.statut = "prêt"
    db.commit()
    return {"statut": cible.statut}


# ─── Génération LM ─────────────────────────────────────────────────────────────

@router.post("/cibles/{cible_id}/generate-lm")
def generate_lm_for_cible(cible_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Génère la lettre de motivation pour une cible et la sauvegarde en base."""
    cible = db.get(CibleSpontanee, cible_id)
    if not cible:
        raise HTTPException(status_code=404, detail="Cible introuvable")

    try:
        lm = generate_lm_spontane(
            employeur=cible.nom,
            secteur=cible.secteur,
            titre_poste=cible.titre_poste,
        )
    except Exception as e:
        logger.error("generate_lm_spontane failed for %s: %s", cible.nom, e)
        raise HTTPException(status_code=500, detail=str(e))

    cible.lm_texte = lm
    cible.statut = "prêt"
    db.commit()
    return {"lm_texte": lm, "statut": cible.statut}


@router.post("/generate-lm-batch")
def generate_lm_batch(
    secteur: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """
    Génère les LM pour toutes les cibles au statut "neuf" ayant un email.
    """
    q = (
        select(CibleSpontanee)
        .where(
            CibleSpontanee.statut == "neuf",
            CibleSpontanee.email.isnot(None),
        )
        .limit(limit)
    )
    if secteur:
        q = q.where(CibleSpontanee.secteur == secteur)

    cibles = db.scalars(q).all()
    generees = 0
    erreurs: list[dict] = []

    for cible in cibles:
        try:
            lm = generate_lm_spontane(
                employeur=cible.nom,
                secteur=cible.secteur,
                titre_poste=cible.titre_poste,
            )
            cible.lm_texte = lm
            cible.statut = "prêt"
            generees += 1
        except Exception as e:
            logger.error("generate_lm batch error for %s: %s", cible.nom, e)
            erreurs.append({"nom": cible.nom, "erreur": str(e)})

    db.commit()
    return {"generees": generees, "erreurs": erreurs}


# ─── Envoi email ───────────────────────────────────────────────────────────────

@router.post("/send-one/{cible_id}")
def send_one(cible_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Envoie la candidature spontanée pour une cible unique."""
    cible = db.get(CibleSpontanee, cible_id)
    if not cible:
        raise HTTPException(status_code=404, detail="Cible introuvable")
    if not cible.email:
        raise HTTPException(status_code=400, detail="Pas d'email pour cette cible")
    if not cible.lm_texte:
        raise HTTPException(
            status_code=400,
            detail="LM non générée — appelez d'abord /cibles/{id}/generate-lm",
        )

    titre_poste = cible.titre_poste or "Candidature Spontanée"
    subject = f"Candidature spontanée — {titre_poste} — {cible.nom}"

    try:
        send_candidature_email(
            to_email=cible.email,
            subject=subject,
            lm_texte=cible.lm_texte,
            cv_path=cible.cv_path,
        )
    except Exception as e:
        cible.statut = "erreur"
        cible.erreur = str(e)
        db.commit()
        logger.error("send_one failed for %s: %s", cible.nom, e)
        raise HTTPException(status_code=500, detail=str(e))

    cible.statut = "envoyé"
    cible.date_envoi = datetime.now()
    cible.erreur = None
    db.commit()
    logger.info("send_one: email envoyé à %s (%s)", cible.email, cible.nom)
    return {"success": True, "email": cible.email, "nom": cible.nom}


@router.post("/send")
def send_batch(
    secteur: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict:
    """
    Envoie les emails pour toutes les cibles au statut "prêt" avec email + LM.
    dry_run=true simule sans envoyer.
    """
    q = (
        select(CibleSpontanee)
        .where(
            CibleSpontanee.statut == "prêt",
            CibleSpontanee.email.isnot(None),
            CibleSpontanee.lm_texte.isnot(None),
        )
        .limit(limit)
    )
    if secteur:
        q = q.where(CibleSpontanee.secteur == secteur)

    cibles = db.scalars(q).all()
    envoyes = 0
    erreurs: list[dict] = []

    for cible in cibles:
        titre_poste = cible.titre_poste or "Candidature Spontanée"
        subject = f"Candidature spontanée — {titre_poste} — {cible.nom}"

        if dry_run:
            logger.info("[dry_run] Envoi simulé : %s → %s", cible.nom, cible.email)
            envoyes += 1
            continue

        try:
            send_candidature_email(
                to_email=cible.email,
                subject=subject,
                lm_texte=cible.lm_texte,
                cv_path=cible.cv_path,
            )
            cible.statut = "envoyé"
            cible.date_envoi = datetime.now()
            cible.erreur = None
            envoyes += 1
            logger.info("send_batch: envoyé à %s (%s)", cible.email, cible.nom)
        except Exception as e:
            cible.statut = "erreur"
            cible.erreur = str(e)
            erreurs.append({"nom": cible.nom, "email": cible.email, "erreur": str(e)})
            logger.error("send_batch error for %s: %s", cible.nom, e)

    db.commit()
    return {
        "envoyes": envoyes,
        "erreurs": erreurs,
        "dry_run": dry_run,
    }


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _to_dict(c: CibleSpontanee) -> dict:
    return {
        "id":               str(c.id),
        "nom":              c.nom,
        "secteur":          c.secteur,
        "type_organisation": c.type_organisation,
        "departement":      c.departement,
        "education_type":   c.education_type,
        "email":            c.email,
        "titre_poste":      c.titre_poste,
        "lm_texte":         c.lm_texte,
        "cv_path":          c.cv_path,
        "statut":           c.statut,
        "erreur":           c.erreur,
        "date_scrape":      c.date_scrape.isoformat() if c.date_scrape else None,
        "date_envoi":       c.date_envoi.isoformat() if c.date_envoi else None,
    }
