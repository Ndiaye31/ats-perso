import uuid
import asyncio
import json
import logging
from datetime import date
from typing import Optional
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.database import get_db
from app.models.candidature import Candidature
from app.models.offer import Offer
from app.profil import profil
from app.logging_utils import log_event
from app.schemas.candidature import CandidatureRead

router = APIRouter(prefix="/candidatures", tags=["candidatures"])
logger = logging.getLogger(__name__)


def _auto_apply_error(code: str, action: str, reason: str) -> str:
    """Format d'erreur normalisé pour auto-apply."""
    return f"{code} | Action: {action} | Reason: {reason}"


def _detect_mode(offer: Offer) -> str:
    """Détermine si la candidature se fait par email, plateforme ou portail tiers.

    Pour emploi.fhf.fr et emploi-territorial.fr : la candidature via la
    plateforme est prioritaire (upload CV + LM). L'email reste accessible
    comme fallback dans l'interface.
    """
    if offer.candidature_url:
        return "portail_tiers"
    if offer.contact_email:
        return "email"
    if offer.url:
        return "plateforme"
    return "inconnu"


class CandidatureWithOffer(CandidatureRead):
    offer_title: str
    offer_company: str
    offer_url: str | None


class CandidatureStatusItem(BaseModel):
    offer_id: uuid.UUID
    statut: str


class CandidatureCreate(BaseModel):
    offer_id: uuid.UUID
    email_contact: str | None = None


class CandidaturePatch(BaseModel):
    statut: str | None = None
    lm_texte: str | None = None
    date_envoi: date | None = None


class GenerateLMResponse(BaseModel):
    lm_texte: str


class BulkCandidaturesRequest(BaseModel):
    candidature_ids: list[uuid.UUID]
    dry_run: bool = False
    max_concurrency: int = 2


class BulkItemResult(BaseModel):
    candidature_id: uuid.UUID
    success: bool
    message: str


class BulkOperationResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: list[BulkItemResult]
    report_path: str | None = None


def _write_bulk_report(operation: str, results: list[BulkItemResult], dry_run: bool = False) -> str | None:
    """Écrit un rapport JSON par batch et retourne son chemin."""
    try:
        from datetime import datetime as _dt

        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path("scripts") / "screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"batch_{operation}_{ts}.json"
        payload = {
            "operation": operation,
            "dry_run": dry_run,
            "total": len(results),
            "success": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "results": [
                {
                    "candidature_id": str(r.candidature_id),
                    "success": r.success,
                    "message": r.message,
                }
                for r in results
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path).replace("\\", "/")
    except Exception:
        return None


def _session_factory_from_db(db: Session):
    return sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)


@router.get("", response_model=list[CandidatureWithOffer])
def list_candidatures(db: Session = Depends(get_db)):
    stmt = (
        select(Candidature)
        .options(joinedload(Candidature.offer))
        .order_by(Candidature.created_at.desc())
    )
    rows = db.execute(stmt).scalars().all()
    result = []
    for c in rows:
        result.append(
            CandidatureWithOffer(
                **CandidatureRead.model_validate(c).model_dump(),
                offer_title=c.offer.title if c.offer else "",
                offer_company=c.offer.company if c.offer else "",
                offer_url=c.offer.url if c.offer else None,
            )
        )
    return result


@router.get("/status-map", response_model=list[CandidatureStatusItem])
def candidature_status_map(db: Session = Depends(get_db)):
    stmt = (
        select(Candidature.offer_id, Candidature.statut, Candidature.created_at)
        .where(Candidature.statut != "annulée")
        .order_by(Candidature.created_at.desc())
    )
    rows = db.execute(stmt).all()

    seen: set[uuid.UUID] = set()
    items: list[CandidatureStatusItem] = []
    for offer_id, statut, _created_at in rows:
        if offer_id in seen:
            continue
        seen.add(offer_id)
        items.append(CandidatureStatusItem(offer_id=offer_id, statut=statut))
    return items


@router.get("/offer/{offer_id}", response_model=CandidatureRead | None)
def get_candidature_by_offer(offer_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retourne la candidature active (non annulée) pour une offre donnée, ou null."""
    row = db.execute(
        select(Candidature)
        .where(Candidature.offer_id == offer_id)
        .where(Candidature.statut != "annulée")
        .order_by(Candidature.created_at.desc())
    ).scalar_one_or_none()
    return row


@router.post("", response_model=CandidatureRead, status_code=201)
def create_candidature(body: CandidatureCreate, db: Session = Depends(get_db)):
    start = perf_counter()
    offer = db.get(Offer, body.offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    # Retourne la candidature existante si elle n'est pas annulée
    existing = db.execute(
        select(Candidature)
        .where(Candidature.offer_id == body.offer_id)
        .where(Candidature.statut != "annulée")
        .order_by(Candidature.created_at.desc())
    ).scalar_one_or_none()
    if existing:
        log_event(
            logger,
            logging.INFO,
            "candidature_create_idempotent",
            offer_id=body.offer_id,
            candidature_id=existing.id,
            source="api",
            duration_ms=round((perf_counter() - start) * 1000, 2),
        )
        return existing
    candidature = Candidature(
        id=uuid.uuid4(),
        offer_id=body.offer_id,
        email_contact=body.email_contact or offer.contact_email,
        statut="brouillon",
        mode_candidature=_detect_mode(offer),
    )
    db.add(candidature)
    db.commit()
    db.refresh(candidature)
    log_event(
        logger,
        logging.INFO,
        "candidature_created",
        offer_id=body.offer_id,
        candidature_id=candidature.id,
        source="api",
        duration_ms=round((perf_counter() - start) * 1000, 2),
    )
    return candidature


@router.patch("/{candidature_id}", response_model=CandidatureRead)
def update_candidature(
    candidature_id: uuid.UUID,
    body: CandidaturePatch,
    db: Session = Depends(get_db),
):
    candidature = db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")
    if body.statut is not None:
        candidature.statut = body.statut
    if body.lm_texte is not None:
        candidature.lm_texte = body.lm_texte
    if body.date_envoi is not None:
        candidature.date_envoi = body.date_envoi
    db.commit()
    db.refresh(candidature)
    return candidature


@router.delete("/{candidature_id}", status_code=204)
def delete_candidature(candidature_id: uuid.UUID, db: Session = Depends(get_db)):
    candidature = db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")
    db.delete(candidature)
    db.commit()


class SendEmailResponse(BaseModel):
    success: bool
    message: str


@router.post("/{candidature_id}/send-email", response_model=SendEmailResponse)
def send_email_endpoint(candidature_id: uuid.UUID, db: Session = Depends(get_db)):
    """Envoie la candidature par email SMTP Gmail (CV en pièce jointe, LM en corps)."""
    start = perf_counter()
    candidature = db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")

    offer = db.get(Offer, candidature.offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    to_email = candidature.email_contact or offer.contact_email
    if not to_email:
        raise HTTPException(status_code=400, detail="Aucun email de contact renseigné")

    from app.config import settings
    from app.email_sender import send_candidature_email
    import smtplib

    subject = f"Candidature — {offer.title}"
    try:
        send_candidature_email(
            to_email=to_email,
            subject=subject,
            lm_texte=candidature.lm_texte or "",
            cv_path=settings.cv_path or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=503, detail="Échec authentification Gmail — vérifiez SMTP_PASSWORD dans .env")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur SMTP : {e}")

    candidature.statut = "envoyée"
    candidature.date_envoi = date.today()
    db.commit()
    log_event(
        logger,
        logging.INFO,
        "candidature_email_sent",
        offer_id=candidature.offer_id,
        candidature_id=candidature_id,
        source="email",
        duration_ms=round((perf_counter() - start) * 1000, 2),
    )
    return SendEmailResponse(success=True, message=f"Email envoyé à {to_email}")


@router.post("/{candidature_id}/generate-lm", response_model=GenerateLMResponse)
def generate_lm_endpoint(
    candidature_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Génère une lettre de motivation via Claude AI et la sauvegarde."""
    start = perf_counter()
    candidature = db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")

    offer = db.get(Offer, candidature.offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    from app.ai.generate_lm import generate_lm
    try:
        lm_texte = generate_lm(
            title=offer.title,
            company=offer.company,
            description=offer.description,
            profil=profil,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur Claude API : {e}")

    candidature.lm_texte = lm_texte
    db.commit()
    log_event(
        logger,
        logging.INFO,
        "candidature_lm_generated",
        offer_id=candidature.offer_id,
        candidature_id=candidature_id,
        source="ai",
        duration_ms=round((perf_counter() - start) * 1000, 2),
    )
    return GenerateLMResponse(lm_texte=lm_texte)


@router.get("/{candidature_id}/download-lm")
def download_lm_pdf(
    candidature_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Génère le PDF de la lettre de motivation et le retourne en téléchargement."""
    candidature = db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")
    if not candidature.lm_texte:
        raise HTTPException(status_code=400, detail="Aucune lettre de motivation générée")

    offer = db.get(Offer, candidature.offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    from app.automation.lm_generator import generate_lm_pdf
    try:
        pdf_path = generate_lm_pdf(
            candidature.lm_texte,
            profil,
            offer.title or "",
            offer.company or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur génération PDF : {e}")

    import re as _re
    slug = _re.sub(r"[^a-zA-Z0-9]+", "_", (offer.company or "")[:30]).strip("_").lower()
    filename = f"lm_{slug}_{date.today().strftime('%Y%m%d')}.pdf"
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
    )


def _generate_lm_with_db(candidature_id: uuid.UUID, db: Session) -> str:
    candidature = db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")

    offer = db.get(Offer, candidature.offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    from app.ai.generate_lm import generate_lm
    try:
        lm_texte = generate_lm(
            title=offer.title,
            company=offer.company,
            description=offer.description,
            profil=profil,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur Claude API : {e}")

    candidature.lm_texte = lm_texte
    db.commit()
    return lm_texte


class AutoApplyResponse(BaseModel):
    success: bool
    message: str
    screenshot_path: Optional[str] = None


def _get_applicator(offer_url: str):
    """Retourne l'applicator correspondant au site de l'offre."""
    from app.automation.emploi_territorial import EmploiTerritorialApplicator
    from app.automation.emploi_fhf import EmploiFHFApplicator
    from app.automation.beetween import BeetweenApplicator

    if not offer_url:
        return None
    if "emploi-territorial.fr" in offer_url:
        return EmploiTerritorialApplicator()
    if "emploi.fhf.fr" in offer_url or "fhf.fr" in offer_url:
        return EmploiFHFApplicator()
    if "beetween.com" in offer_url:
        return BeetweenApplicator()
    if "hellowork.com" in offer_url:
        from app.automation.hellowork import HelloWorkApplicator
        return HelloWorkApplicator()
    return None


async def _run_step_with_retries(
    step_name: str,
    attempts: int,
    delay_s: float,
    step_callable,
) -> bool:
    """Exécute une étape async booléenne avec retry borné."""
    total = max(1, int(attempts))
    wait = max(0.0, float(delay_s))
    for i in range(total):
        try:
            ok = await step_callable()
            if ok:
                return True
        except Exception as e:
            print(f"[auto-apply][{step_name}] tentative {i + 1}/{total} erreur: {e}")
        if i < total - 1 and wait > 0:
            await asyncio.sleep(wait)
    return False


@router.post("/{candidature_id}/auto-apply", response_model=AutoApplyResponse)
async def auto_apply(
    candidature_id: uuid.UUID,
    dry_run: bool = False,
    db: Session = Depends(get_db),
):
    """Lance la candidature automatique via Playwright.
    dry_run=true : screenshot uniquement, pas de soumission.
    """
    return await _auto_apply_with_db(candidature_id, dry_run, db)


async def _auto_apply_with_db(
    candidature_id: uuid.UUID,
    dry_run: bool,
    db: Session,
) -> AutoApplyResponse:
    start = perf_counter()
    candidature = db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(
            status_code=404,
            detail=_auto_apply_error(
                "AUTOAPPLY_CANDIDATURE_NOT_FOUND",
                "Vérifier l'ID de candidature puis relancer.",
                "Candidature not found",
            ),
        )

    offer = db.get(Offer, candidature.offer_id)
    if not offer or not offer.url:
        raise HTTPException(
            status_code=404,
            detail=_auto_apply_error(
                "AUTOAPPLY_OFFER_URL_NOT_FOUND",
                "Vérifier que l'offre existe et que son URL est renseignée.",
                "Offre ou URL introuvable",
            ),
        )

    # Si la candidature doit se faire par email, on interdit l'auto-apply navigateur.
    if candidature.mode_candidature == "email":
        raise HTTPException(
            status_code=400,
            detail=_auto_apply_error(
                "AUTOAPPLY_EMAIL_MODE_BLOCKED",
                "Utiliser /send-email pour cette candidature.",
                "Candidature par email: auto-apply indisponible pour cette offre",
            ),
        )

    if offer.candidature_url:
        # Vérifier si le portail tiers est supporté par un applicator
        tiers_applicator = _get_applicator(offer.candidature_url)
        if not tiers_applicator:
            raise HTTPException(
                status_code=400,
                detail=_auto_apply_error(
                    "AUTOAPPLY_PORTAIL_TIERS_BLOCKED",
                    "Candidater manuellement sur le portail tiers indiqué.",
                    f"Candidature via portail tiers uniquement : {offer.candidature_url}",
                ),
            )

    applicator = _get_applicator(offer.candidature_url or offer.url)
    if not applicator:
        # Site non supporté : on vérifie en plus que le mode est plateforme
        if candidature.mode_candidature != "plateforme":
            raise HTTPException(
                status_code=400,
                detail=_auto_apply_error(
                    "AUTOAPPLY_MODE_NOT_COMPATIBLE",
                    "Basculer vers un workflow compatible (email ou plateforme supportée).",
                    f"Site non supporté et mode '{candidature.mode_candidature}' non automatisable",
                ),
            )
        raise HTTPException(
            status_code=400,
            detail=_auto_apply_error(
                "AUTOAPPLY_UNSUPPORTED_SITE",
                "Candidater manuellement ou implémenter un applicator pour ce domaine.",
                f"Site non supporté pour l'automatisation : {offer.url}",
            ),
        )

    from app.config import settings
    from playwright.async_api import async_playwright
    step_retries = max(1, settings.auto_apply_step_retries)
    retry_delay_s = max(0.0, settings.auto_apply_retry_delay_s)

    if not settings.cv_path:
        raise HTTPException(
            status_code=503,
            detail=_auto_apply_error(
                "AUTOAPPLY_MISSING_CV_PATH",
                "Renseigner CV_PATH dans .env puis redémarrer l'API.",
                "CV_PATH non configuré dans .env",
            ),
        )

    # URL effective pour la candidature (portail tiers ou offre directe)
    apply_url = offer.candidature_url or offer.url

    # Récupère les credentials selon le site (certains portails n'en ont pas besoin)
    login = ""
    password = ""
    needs_credentials = True
    if "beetween.com" in apply_url:
        needs_credentials = False
    elif "hellowork.com" in (offer.url or "") or "hellowork.com" in apply_url:
        login = settings.hellowork_login
        password = settings.hellowork_password
    elif "emploi-territorial.fr" in (offer.url or ""):
        login = settings.emploi_territorial_login
        password = settings.emploi_territorial_password
    else:
        login = settings.emploi_fhf_login
        password = settings.emploi_fhf_password

    if needs_credentials and (not login or not password):
        raise HTTPException(
            status_code=503,
            detail=_auto_apply_error(
                "AUTOAPPLY_MISSING_CREDENTIALS",
                "Renseigner les identifiants de la plateforme ciblée dans .env.",
                "Credentials non configurés dans .env",
            ),
        )

    lm_texte = candidature.lm_texte or ""
    screenshot_path = None

    # Slug lisible pour le nom du fichier : société + date
    import re as _re
    from datetime import datetime as _dt
    _slug = _re.sub(r"[^a-zA-Z0-9]+", "_", (offer.company or "inconnu"))[:30].strip("_").lower()
    _today = _dt.now().strftime("%Y%m%d")
    _prefix = f"scripts/screenshots/{_slug}_{_today}"

    async def _capture_failure(page_obj, suffix: str) -> str | None:
        """Capture best-effort, sans faire échouer le flux si screenshot KO."""
        path = f"{_prefix}_{suffix}.png"
        try:
            if page_obj is not None:
                await applicator.screenshot(page_obj, path)
                return path
        except Exception:
            pass
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Login
            ok = await _run_step_with_retries(
                "login",
                step_retries,
                retry_delay_s,
                lambda: applicator.login(page, login, password),
            )
            if not ok:
                screenshot_path = await _capture_failure(page, "login_echec")
                await browser.close()
                return AutoApplyResponse(
                    success=False,
                    message=_auto_apply_error(
                        "AUTOAPPLY_LOGIN_FAILED",
                        "Vérifier identifiants, MFA/captcha, puis relancer.",
                        "Échec de la connexion",
                    ),
                    screenshot_path=screenshot_path,
                )

            # Navigation vers l'offre
            ok = await _run_step_with_retries(
                "navigate_to_offer",
                step_retries,
                retry_delay_s,
                lambda: applicator.navigate_to_offer(page, apply_url),
            )
            if not ok:
                screenshot_path = await _capture_failure(page, "navigation_echec")
                await browser.close()
                return AutoApplyResponse(
                    success=False,
                    message=_auto_apply_error(
                        "AUTOAPPLY_NAVIGATION_FAILED",
                        "Vérifier l'URL de l'offre et sa disponibilité.",
                        "Impossible de naviguer vers l'offre",
                    ),
                    screenshot_path=screenshot_path,
                )

            # Cherche le bouton Postuler
            ok = await _run_step_with_retries(
                "find_apply_button",
                step_retries,
                retry_delay_s,
                lambda: applicator.find_apply_button(page),
            )
            if not ok:
                # Fallback email : si le bouton n'existe pas mais qu'un email est dispo
                fallback_email = candidature.email_contact or (offer.contact_email if offer else None)
                if fallback_email:
                    await browser.close()
                    from app.config import settings as _settings
                    from app.email_sender import send_candidature_email
                    lm_body = candidature.lm_texte or ""
                    subject = f"Candidature — {offer.title}"
                    try:
                        send_candidature_email(
                            to_email=fallback_email,
                            subject=subject,
                            lm_texte=lm_body,
                            cv_path=_settings.cv_path or None,
                        )
                    except Exception as e:
                        return AutoApplyResponse(
                            success=False,
                            message=_auto_apply_error(
                                "AUTOAPPLY_EMAIL_FALLBACK_FAILED",
                                "Vérifier la configuration SMTP et l'adresse email.",
                                f"Bouton Postuler absent, fallback email échoué : {e}",
                            ),
                        )
                    candidature.statut = "envoyée"
                    candidature.mode_candidature = "email"
                    candidature.date_envoi = date.today()
                    db.commit()
                    log_event(
                        logger,
                        logging.INFO,
                        "candidature_auto_apply_email_fallback",
                        offer_id=candidature.offer_id,
                        candidature_id=candidature_id,
                        source=f"email_fallback:{fallback_email}",
                        duration_ms=round((perf_counter() - start) * 1000, 2),
                    )
                    return AutoApplyResponse(
                        success=True,
                        message=f"Bouton Postuler absent — email envoyé à {fallback_email}",
                    )

                screenshot_path = f"{_prefix}_bouton_introuvable.png"
                await applicator.screenshot(page, screenshot_path)
                await browser.close()
                return AutoApplyResponse(
                    success=False,
                    message=_auto_apply_error(
                        "AUTOAPPLY_APPLY_BUTTON_NOT_FOUND",
                        "Mettre à jour les sélecteurs du site cible.",
                        "Bouton Postuler non trouvé et aucun email de contact disponible",
                    ),
                    screenshot_path=screenshot_path,
                )

            if dry_run:
                screenshot_path = f"{_prefix}_dry_run.png"
                await applicator.screenshot(page, screenshot_path)
                await browser.close()
                return AutoApplyResponse(
                    success=True,
                    message="Dry-run : screenshot pris, aucune soumission effectuée",
                    screenshot_path=screenshot_path,
                )

            # Remplissage du formulaire
            ok = await _run_step_with_retries(
                "fill_form",
                step_retries,
                retry_delay_s,
                lambda: applicator.fill_form(
                    page, lm_texte, settings.cv_path,
                    profil=profil,
                    offer_title=offer.title or "",
                    offer_company=offer.company or "",
                ),
            )
            if not ok:
                screenshot_path = f"{_prefix}_erreur_formulaire.png"
                await applicator.screenshot(page, screenshot_path)
                await browser.close()
                return AutoApplyResponse(
                    success=False,
                    message=_auto_apply_error(
                        "AUTOAPPLY_FORM_FILL_FAILED",
                        "Vérifier les champs requis (CV, diplôme, LM) et leurs sélecteurs.",
                        "Erreur lors du remplissage du formulaire",
                    ),
                    screenshot_path=screenshot_path,
                )

            # Soumission
            ok = await _run_step_with_retries(
                "submit",
                step_retries,
                retry_delay_s,
                lambda: applicator.submit(page),
            )

            if ok:
                await browser.close()
                candidature.statut = "envoyée"
                candidature.date_envoi = date.today()
                db.commit()
                log_event(
                    logger,
                    logging.INFO,
                    "candidature_auto_apply_success",
                    offer_id=candidature.offer_id,
                    candidature_id=candidature_id,
                    source=offer.url,
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                    dry_run=dry_run,
                )
                return AutoApplyResponse(success=True, message="Candidature envoyée avec succès")
            else:
                screenshot_path = await _capture_failure(page, "soumission_echec")
                await browser.close()
                log_event(
                    logger,
                    logging.WARNING,
                    "candidature_auto_apply_submit_failed",
                    offer_id=candidature.offer_id,
                    candidature_id=candidature_id,
                    source=offer.url,
                    duration_ms=round((perf_counter() - start) * 1000, 2),
                    dry_run=dry_run,
                )
                return AutoApplyResponse(
                    success=False,
                    message=_auto_apply_error(
                        "AUTOAPPLY_SUBMIT_FAILED",
                        "Vérifier les validations côté plateforme après soumission.",
                        "Échec de la soumission du formulaire",
                    ),
                    screenshot_path=screenshot_path,
                )

    except Exception as e:
        screenshot_path = None
        try:
            screenshot_path = await _capture_failure(locals().get("page"), "unexpected_error")
        except Exception:
            screenshot_path = None
        log_event(
            logger,
            logging.ERROR,
            "candidature_auto_apply_error",
            offer_id=(candidature.offer_id if candidature else None),
            candidature_id=candidature_id,
            source=(offer.url if "offer" in locals() and offer else None),
            duration_ms=round((perf_counter() - start) * 1000, 2),
            error=str(e),
            dry_run=dry_run,
        )
        raise HTTPException(
            status_code=500,
            detail=_auto_apply_error(
                "AUTOAPPLY_PLAYWRIGHT_ERROR",
                "Consulter les logs et vérifier l'environnement Playwright.",
                f"Erreur Playwright : {e}" + (f" | screenshot={screenshot_path}" if screenshot_path else ""),
            ),
        )


def _bulk_generate_lm_impl(ids: list[uuid.UUID], session_factory) -> BulkOperationResponse:
    results: list[BulkItemResult] = []

    for candidature_id in ids:
        db = session_factory()
        try:
            _generate_lm_with_db(candidature_id, db)
            results.append(
                BulkItemResult(
                    candidature_id=candidature_id,
                    success=True,
                    message="LM générée",
                )
            )
        except HTTPException as e:
            results.append(
                BulkItemResult(
                    candidature_id=candidature_id,
                    success=False,
                    message=str(e.detail),
                )
            )
        except Exception as e:
            results.append(
                BulkItemResult(
                    candidature_id=candidature_id,
                    success=False,
                    message=f"Erreur: {e}",
                )
            )
        finally:
            db.close()

    success_count = sum(1 for r in results if r.success)
    report_path = _write_bulk_report("generate_lm", results, dry_run=False)
    return BulkOperationResponse(
        total=len(ids),
        success=success_count,
        failed=len(ids) - success_count,
        results=results,
        report_path=report_path,
    )


async def _bulk_auto_apply_impl(
    ids: list[uuid.UUID],
    dry_run: bool,
    max_concurrency: int,
    session_factory,
) -> BulkOperationResponse:
    results: list[BulkItemResult] = []
    semaphore = asyncio.Semaphore(max(1, min(5, max_concurrency)))

    async def _run_one(candidature_id: uuid.UUID):
        async with semaphore:
            db = session_factory()
            try:
                response = await _auto_apply_with_db(candidature_id, dry_run, db)
                return BulkItemResult(
                    candidature_id=candidature_id,
                    success=response.success,
                    message=response.message,
                )
            except HTTPException as e:
                return BulkItemResult(
                    candidature_id=candidature_id,
                    success=False,
                    message=str(e.detail),
                )
            except Exception as e:
                return BulkItemResult(
                    candidature_id=candidature_id,
                    success=False,
                    message=f"Erreur: {e}",
                )
            finally:
                db.close()

    if ids:
        results = await asyncio.gather(*[_run_one(c_id) for c_id in ids])

    success_count = sum(1 for r in results if r.success)
    report_path = _write_bulk_report("auto_apply", results, dry_run=dry_run)
    return BulkOperationResponse(
        total=len(ids),
        success=success_count,
        failed=len(ids) - success_count,
        results=results,
        report_path=report_path,
    )


@router.post("/bulk-generate-lm", response_model=BulkOperationResponse)
def bulk_generate_lm(body: BulkCandidaturesRequest, db: Session = Depends(get_db)):
    ids = list(dict.fromkeys(body.candidature_ids))
    session_factory = _session_factory_from_db(db)
    return _bulk_generate_lm_impl(ids, session_factory)


@router.post("/bulk-auto-apply", response_model=BulkOperationResponse)
async def bulk_auto_apply(body: BulkCandidaturesRequest, db: Session = Depends(get_db)):
    ids = list(dict.fromkeys(body.candidature_ids))
    session_factory = _session_factory_from_db(db)
    return await _bulk_auto_apply_impl(
        ids=ids,
        dry_run=body.dry_run,
        max_concurrency=body.max_concurrency,
        session_factory=session_factory,
    )


@router.post("/bulk-generate-lm-and-auto-apply", response_model=BulkOperationResponse)
async def bulk_generate_lm_and_auto_apply(body: BulkCandidaturesRequest, db: Session = Depends(get_db)):
    ids = list(dict.fromkeys(body.candidature_ids))
    session_factory = _session_factory_from_db(db)
    lm_result = _bulk_generate_lm_impl(ids, session_factory)
    success_ids = [r.candidature_id for r in lm_result.results if r.success]
    if not success_ids:
        merged_results = [
            BulkItemResult(
                candidature_id=r.candidature_id,
                success=False,
                message=f"LM KO: {r.message}",
            )
            for r in lm_result.results
        ]
        report_path = _write_bulk_report("generate_lm_and_auto_apply", merged_results, dry_run=body.dry_run)
        return BulkOperationResponse(
            total=lm_result.total,
            success=0,
            failed=lm_result.total,
            results=merged_results,
            report_path=report_path,
        )

    auto_result = await _bulk_auto_apply_impl(
        ids=success_ids,
        dry_run=body.dry_run,
        max_concurrency=body.max_concurrency,
        session_factory=session_factory,
    )
    auto_map = {r.candidature_id: r for r in auto_result.results}

    merged: list[BulkItemResult] = []
    for r in lm_result.results:
        if not r.success:
            merged.append(
                BulkItemResult(
                    candidature_id=r.candidature_id,
                    success=False,
                    message=f"LM KO: {r.message}",
                )
            )
            continue
        ar = auto_map.get(r.candidature_id)
        if not ar:
            merged.append(
                BulkItemResult(
                    candidature_id=r.candidature_id,
                    success=False,
                    message="Auto-apply KO: résultat introuvable",
                )
            )
            continue
        merged.append(
            BulkItemResult(
                candidature_id=r.candidature_id,
                success=ar.success,
                message=("OK" if ar.success else "Auto-apply KO") + f": {ar.message}",
            )
        )

    success_count = sum(1 for r in merged if r.success)
    report_path = _write_bulk_report("generate_lm_and_auto_apply", merged, dry_run=body.dry_run)
    return BulkOperationResponse(
        total=len(merged),
        success=success_count,
        failed=len(merged) - success_count,
        results=merged,
        report_path=report_path,
    )
