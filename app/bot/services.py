"""
Wrappers async pour la couche service du bot Telegram.
Chaque fonction crée/ferme sa propre session SQLAlchemy (thread-safety).
Pattern identique à app/scheduler.py.
"""
import asyncio
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func

from app.models.cible_spontanee import CibleSpontanee
from app.models.candidature import Candidature


# ─── Stats ────────────────────────────────────────────────────────────────────

def _get_stats_sync() -> dict:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        rows = db.execute(
            select(CibleSpontanee.statut, func.count().label("n"))
            .group_by(CibleSpontanee.statut)
        ).all()
        stats = {r.statut: r.n for r in rows}
        stats["total"] = sum(stats.values())

        # Stats par secteur
        rows_sect = db.execute(
            select(CibleSpontanee.secteur, func.count().label("n"))
            .group_by(CibleSpontanee.secteur)
        ).all()
        stats["par_secteur"] = {r.secteur: r.n for r in rows_sect}
        return stats
    finally:
        db.close()


async def get_stats() -> dict:
    return await asyncio.to_thread(_get_stats_sync)


def _get_pipeline_sync() -> dict:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Candidature.statut, func.count().label("n"))
            .group_by(Candidature.statut)
        ).all()
        stats = {r.statut: r.n for r in rows}
        stats["total"] = sum(stats.values())
        return stats
    finally:
        db.close()


async def get_pipeline() -> dict:
    return await asyncio.to_thread(_get_pipeline_sync)


# ─── Cibles ───────────────────────────────────────────────────────────────────

def _list_cibles_sync(
    statut: Optional[str],
    limit: int,
    departement: Optional[str] = None,
    secteur: Optional[str] = None,
) -> list[dict]:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        q = select(CibleSpontanee).order_by(CibleSpontanee.created_at.desc()).limit(limit)
        if statut:
            q = q.where(CibleSpontanee.statut == statut)
        if departement:
            q = q.where(CibleSpontanee.departement == departement)
        if secteur:
            q = q.where(CibleSpontanee.secteur == secteur)
        cibles = db.scalars(q).all()
        return [_cible_to_dict(c) for c in cibles]
    finally:
        db.close()


async def list_cibles(
    statut: Optional[str] = None,
    limit: int = 15,
    departement: Optional[str] = None,
    secteur: Optional[str] = None,
) -> list[dict]:
    return await asyncio.to_thread(_list_cibles_sync, statut, limit, departement, secteur)


def _get_cible_by_id_sync(cible_id: str) -> Optional[dict]:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        c = db.get(CibleSpontanee, uuid.UUID(cible_id))
        return _cible_to_dict(c) if c else None
    finally:
        db.close()


async def get_cible_by_id(cible_id: str) -> Optional[dict]:
    return await asyncio.to_thread(_get_cible_by_id_sync, cible_id)


def _get_cible_by_prefix_sync(prefix: str) -> Optional[dict]:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        cibles = db.scalars(select(CibleSpontanee)).all()
        matches = [c for c in cibles if str(c.id).startswith(prefix)]
        if len(matches) == 0:
            return None
        if len(matches) > 1:
            return {"ambiguous": True, "count": len(matches)}
        return _cible_to_dict(matches[0])
    finally:
        db.close()


async def get_cible_by_prefix(prefix: str) -> Optional[dict]:
    return await asyncio.to_thread(_get_cible_by_prefix_sync, prefix)


def _cible_to_dict(c: CibleSpontanee) -> dict:
    return {
        "id": str(c.id),
        "nom": c.nom,
        "secteur": c.secteur,
        "type_organisation": c.type_organisation,
        "departement": c.departement,
        "email": c.email,
        "statut": c.statut,
        "titre_poste": c.titre_poste,
        "lm_texte": c.lm_texte,
        "cv_path": c.cv_path,
        "date_envoi": c.date_envoi.strftime("%d/%m/%Y") if c.date_envoi else None,
    }


# ─── Génération LM ────────────────────────────────────────────────────────────

def _generate_lm_for_sync(cible_id: str) -> dict:
    from app.database import SessionLocal
    from app.ai.lm_spontane import generate_lm_spontane
    db = SessionLocal()
    try:
        cible = db.get(CibleSpontanee, uuid.UUID(cible_id))
        if not cible:
            return {"error": "Cible introuvable"}
        lm = generate_lm_spontane(
            employeur=cible.nom,
            secteur=cible.secteur,
            titre_poste=cible.titre_poste,
        )
        cible.lm_texte = lm
        cible.statut = "prêt"
        db.commit()
        return {"lm_texte": lm, "nom": cible.nom, "id": str(cible.id)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


async def generate_lm_for(cible_id: str) -> dict:
    return await asyncio.to_thread(_generate_lm_for_sync, cible_id)


def _generate_batch_sync(limit: int, departement: Optional[str] = None) -> dict:
    from app.database import SessionLocal
    from app.ai.lm_spontane import generate_lm_spontane
    db = SessionLocal()
    try:
        q = (
            select(CibleSpontanee)
            .where(
                CibleSpontanee.statut == "neuf",
                CibleSpontanee.email.isnot(None),
            )
            .limit(limit)
        )
        if departement:
            q = q.where(CibleSpontanee.departement == departement)
        cibles = db.scalars(q).all()
        generees = 0
        erreurs: list[str] = []
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
                erreurs.append(f"{cible.nom}: {e}")
        db.commit()
        return {"generees": generees, "erreurs": erreurs}
    finally:
        db.close()


async def generate_batch(limit: int = 10, departement: Optional[str] = None) -> dict:
    return await asyncio.to_thread(_generate_batch_sync, limit, departement)


# ─── Envoi email ──────────────────────────────────────────────────────────────

def _send_one_sync(cible_id: str) -> dict:
    from app.database import SessionLocal
    from app.email_sender import send_candidature_email
    db = SessionLocal()
    try:
        cible = db.get(CibleSpontanee, uuid.UUID(cible_id))
        if not cible:
            return {"error": "Cible introuvable"}
        if not cible.email:
            return {"error": "Pas d'email pour cette cible"}
        if not cible.lm_texte:
            return {"error": "LM non générée — utilisez Générer LM d'abord"}

        titre_poste = cible.titre_poste or "Candidature Spontanée"
        subject = f"Candidature spontanée — {titre_poste} — {cible.nom}"

        send_candidature_email(
            to_email=cible.email,
            subject=subject,
            lm_texte=cible.lm_texte,
            cv_path=cible.cv_path,
        )
        cible.statut = "envoyé"
        cible.date_envoi = datetime.now()
        cible.erreur = None
        db.commit()
        return {"success": True, "nom": cible.nom, "email": cible.email}
    except Exception as e:
        try:
            cible.statut = "erreur"
            cible.erreur = str(e)
            db.commit()
        except Exception:
            pass
        return {"error": str(e)}
    finally:
        db.close()


async def send_one(cible_id: str) -> dict:
    return await asyncio.to_thread(_send_one_sync, cible_id)


def _send_batch_sync(limit: int) -> dict:
    from app.database import SessionLocal
    from app.email_sender import send_candidature_email
    db = SessionLocal()
    try:
        cibles = db.scalars(
            select(CibleSpontanee)
            .where(
                CibleSpontanee.statut == "prêt",
                CibleSpontanee.email.isnot(None),
                CibleSpontanee.lm_texte.isnot(None),
            )
            .limit(limit)
        ).all()
        envoyes = 0
        erreurs: list[str] = []
        for cible in cibles:
            titre_poste = cible.titre_poste or "Candidature Spontanée"
            subject = f"Candidature spontanée — {titre_poste} — {cible.nom}"
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
            except Exception as e:
                cible.statut = "erreur"
                cible.erreur = str(e)
                erreurs.append(f"{cible.nom}: {e}")
        db.commit()
        return {"envoyes": envoyes, "erreurs": erreurs}
    finally:
        db.close()


async def send_batch(limit: int = 20) -> dict:
    return await asyncio.to_thread(_send_batch_sync, limit)


# ─── Scraping ─────────────────────────────────────────────────────────────────

def _run_scrape_sync(secteur: Optional[str]) -> dict:
    from app.database import SessionLocal
    from app.scrapers.mairies import scrape_mairies
    from app.scrapers.education import scrape_education
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    CV_PAR_SECTEUR = {
        "mairies": str(BASE_DIR / "config" / "cv_mairies.pdf"),
        "education": str(BASE_DIR / "config" / "cv_education.pdf"),
    }

    resultats = []
    if secteur in (None, "mairies"):
        resultats.extend(scrape_mairies())
    if secteur in (None, "education"):
        resultats.extend(scrape_education())

    db = SessionLocal()
    try:
        inseres = 0
        ignores = 0
        for item in resultats:
            existant = db.scalar(
                select(CibleSpontanee).where(
                    CibleSpontanee.nom == item["nom"],
                    CibleSpontanee.secteur == item["secteur"],
                )
            )
            if existant:
                ignores += 1
                continue
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
                date_scrape=datetime.now(),
            )
            db.add(cible)
            inseres += 1
        db.commit()
        return {"inseres": inseres, "ignores": ignores, "total": inseres + ignores}
    finally:
        db.close()


async def run_scrape(secteur: Optional[str] = None) -> dict:
    return await asyncio.to_thread(_run_scrape_sync, secteur)
