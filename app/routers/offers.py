import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.offer import Offer
from app.models.source import Source
from app.schemas.offer import OfferRead, OfferTableResponse

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("", response_model=list[OfferRead])
def list_offers(
    min_score: int = Query(default=0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Offer)
        .options(joinedload(Offer.source))
        .order_by(Offer.score.desc().nulls_last(), Offer.created_at.desc())
    )
    if min_score > 0:
        stmt = stmt.where(Offer.score >= min_score)
    offers = db.execute(stmt).scalars().all()
    return offers


def _mode_expr():
    return case(
        (Offer.candidature_url.isnot(None), "portail_tiers"),
        (Offer.url.ilike("%emploi.fhf.fr%"), "plateforme"),
        (Offer.contact_email.isnot(None), "email"),
        (Offer.url.isnot(None), "plateforme"),
        else_="inconnu",
    )


@router.get("/table", response_model=OfferTableResponse)
def list_offers_table(
    min_score: int = Query(default=0, ge=0, le=100),
    status: str = Query(default="all"),
    source: str = Query(default="all"),
    mode: str = Query(default="all"),
    location_q: str = Query(default="", max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    conditions = []

    if min_score > 0:
        conditions.append(Offer.score >= min_score)
    if status != "all":
        conditions.append(Offer.status == status)
    if source != "all":
        conditions.append(Offer.source.has(Source.name == source))
    if mode != "all":
        conditions.append(_mode_expr() == mode)
    if location_q.strip():
        conditions.append(Offer.location.ilike(f"%{location_q.strip()}%"))

    total_stmt = select(func.count()).select_from(Offer)
    if conditions:
        total_stmt = total_stmt.where(*conditions)
    total = db.execute(total_stmt).scalar_one()

    stmt = (
        select(Offer)
        .options(joinedload(Offer.source))
        .order_by(Offer.score.desc().nulls_last(), Offer.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if conditions:
        stmt = stmt.where(*conditions)

    items = db.execute(stmt).scalars().all()
    return OfferTableResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{offer_id}", response_model=OfferRead)
def get_offer_detail(offer_id: uuid.UUID, db: Session = Depends(get_db)):
    stmt = (
        select(Offer)
        .options(joinedload(Offer.source))
        .where(Offer.id == offer_id)
    )
    offer = db.execute(stmt).scalar_one_or_none()
    if not offer:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Offer not found")
    return offer
