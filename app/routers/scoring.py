from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.offer import Offer
from app.profil import profil
from app.scoring import MIN_SCORE, score_offer

router = APIRouter(prefix="/offres", tags=["scoring"])


@router.post("/score")
def rescore_all(db: Session = Depends(get_db)) -> dict:
    """Re-calcule le score de toutes les offres et supprime celles sous le seuil."""
    offers = db.execute(select(Offer)).scalars().all()
    scored = purged = 0
    for offer in offers:
        s, details = score_offer(offer, profil)
        if s < MIN_SCORE:
            db.delete(offer)
            purged += 1
        else:
            offer.score = s
            offer.score_details = details
            scored += 1
    db.commit()
    return {"scored": scored, "purged": purged}
