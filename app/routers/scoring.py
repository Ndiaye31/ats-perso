from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.offer import Offer
from app.profil import profil
from app.scoring import MIN_SCORE, score_offer

router = APIRouter(prefix="/offres", tags=["scoring"])


def _is_expired(offer: Offer) -> bool:
    """Retourne True si la date limite est dépassée (format DD/MM/YYYY)."""
    if not offer.date_limite:
        return False
    try:
        d = date(
            int(offer.date_limite[6:10]),
            int(offer.date_limite[3:5]),
            int(offer.date_limite[0:2]),
        )
        return d < date.today()
    except (ValueError, IndexError):
        return False


@router.post("/score")
def rescore_all(db: Session = Depends(get_db)) -> dict:
    """Re-calcule le score de toutes les offres et supprime celles sous le seuil ou expirées."""
    offers = db.execute(select(Offer)).scalars().all()
    scored = purged = expired = 0
    for offer in offers:
        if _is_expired(offer):
            db.delete(offer)
            expired += 1
            continue
        s, details = score_offer(offer, profil)
        if s < MIN_SCORE:
            db.delete(offer)
            purged += 1
        else:
            offer.score = s
            offer.score_details = details
            scored += 1
    db.commit()
    return {"scored": scored, "purged": purged, "expired": expired}
