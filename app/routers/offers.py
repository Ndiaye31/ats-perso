import logging
import re
import uuid
from datetime import date

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.candidature import Candidature
from app.models.offer import Offer
from app.models.source import Source
from app.schemas.offer import (
    OfferCreate,
    OfferDetectRequest,
    OfferDetectResponse,
    OfferRead,
    OfferTableResponse,
    OfferUpdate,
)
from app.utils import compute_content_hash

logger = logging.getLogger(__name__)

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
    # Exclure les offres ayant une candidature envoyée (visibles uniquement dans Candidatures)
    sent_offer_ids = (
        select(Candidature.offer_id)
        .where(Candidature.statut == "envoyée")
        .scalar_subquery()
    )

    # Exclure les offres dont la date limite est dépassée (format dd/mm/yyyy)
    today_str = date.today().strftime("%d/%m/%Y")
    not_expired = or_(
        Offer.date_limite.is_(None),
        func.to_date(Offer.date_limite, "DD/MM/YYYY") >= date.today(),
    )

    conditions = [Offer.id.notin_(sent_offer_ids), not_expired]

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


@router.post("/detect", response_model=OfferDetectResponse)
def detect_offer_from_url(payload: OfferDetectRequest):
    """Fetch une URL et extrait les métadonnées de l'offre."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(payload.url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=422, detail=f"Impossible de charger l'URL : {e}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Title: og:title > <title> > h1
    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    if not title and soup.title:
        title = soup.title.get_text(strip=True)
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Description: og:description > meta description > first large text block
    description = None
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        description = og_desc["content"].strip()
    if not description:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            description = meta_desc["content"].strip()

    # Detailed description from page body (emploi-territorial style or generic)
    body_desc = None
    for sel in (".offre-description", ".job-description", "#description", "article"):
        el = soup.select_one(sel)
        if el:
            body_desc = el.get_text(separator="\n", strip=True)
            break
    if body_desc and (not description or len(body_desc) > len(description)):
        description = body_desc

    # Company: structured data or meta
    company = None
    for row in soup.select(".offre-item"):
        label_el = row.select_one(".offre-item-label, .offre-item-text:first-child")
        label = label_el.get_text(strip=True).lower() if label_el else ""
        if any(kw in label for kw in ("employeur", "entreprise", "organisme", "établissement")):
            val_el = row.select_one(".offre-item-value, .offre-item-text:last-child")
            if val_el:
                company = val_el.get_text(strip=True)
            break
    if not company:
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            company = og_site["content"].strip()

    # Location
    location = None
    for row in soup.select(".offre-item"):
        label_el = row.select_one(".offre-item-label, .offre-item-text:first-child")
        label = label_el.get_text(strip=True).lower() if label_el else ""
        if any(kw in label for kw in ("lieu", "localisation", "ville", "département")):
            val_el = row.select_one(".offre-item-value, .offre-item-text:last-child")
            if val_el:
                location = val_el.get_text(strip=True)
            break

    # Email
    email = None
    for row in soup.select(".offre-item"):
        label_el = row.select_one(".offre-item-label, .offre-item-text:first-child")
        label = label_el.get_text(strip=True).lower() if label_el else ""
        if any(kw in label for kw in ("contact", "information", "renseignement")):
            val_el = row.select_one(".offre-item-value, .offre-item-text:last-child")
            mailto = val_el.select_one("a[href^='mailto:']") if val_el else None
            if mailto:
                email = mailto["href"].replace("mailto:", "").strip() or None
            elif val_el:
                match = re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", val_el.get_text())
                if match:
                    email = match.group()
            break
    # Cloudflare email protection
    if not email:
        for a in soup.select("a[href*='email-protection']"):
            encoded = a.get("href", "").split("#")[-1]
            try:
                key = int(encoded[:2], 16)
                decoded = "".join(chr(int(encoded[i:i+2], 16) ^ key) for i in range(2, len(encoded), 2))
                if "@" in decoded:
                    email = decoded
                    break
            except Exception:
                pass
    if not email:
        mailto = soup.select_one("a[href^='mailto:']")
        if mailto:
            email = mailto["href"].replace("mailto:", "").strip() or None

    # Date limite
    date_limite = None
    for row in soup.select(".offre-item"):
        label_el = row.select_one(".offre-item-label, .offre-item-text:first-child")
        label = label_el.get_text(strip=True).lower() if label_el else ""
        if "date limite" in label:
            val_el = row.select_one(".offre-item-value, .offre-item-text:last-child")
            if val_el:
                m = re.search(r"(\d{2}/\d{2}/\d{4})", val_el.get_text(strip=True))
                if m:
                    date_limite = m.group(1)
            break

    # Candidature URL (external portal link)
    candidature_url = None
    base_domain = payload.url.replace("https://", "").replace("http://", "").split("/")[0]
    for row in soup.select(".offre-item"):
        label_el = row.select_one(".offre-item-label, .offre-item-text:first-child")
        label = label_el.get_text(strip=True).lower() if label_el else ""
        if "lien de candidature" in label:
            val_el = row.select_one(".offre-item-value, .offre-item-text:last-child")
            if val_el:
                a = val_el.select_one("a[href]")
                if a:
                    href = str(a.get("href", ""))
                    link_domain = href.replace("https://", "").replace("http://", "").split("/")[0]
                    if link_domain != base_domain:
                        candidature_url = href
            break

    return OfferDetectResponse(
        title=title,
        company=company,
        location=location,
        description=description,
        date_limite=date_limite,
        contact_email=email,
        candidature_url=candidature_url,
    )


@router.post("", response_model=OfferRead, status_code=201)
def create_offer(payload: OfferCreate, db: Session = Depends(get_db)):
    offer = Offer(
        **payload.model_dump(),
        content_hash=compute_content_hash(payload.title, payload.company, payload.location),
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


@router.patch("/{offer_id}", response_model=OfferRead)
def update_offer(offer_id: uuid.UUID, payload: OfferUpdate, db: Session = Depends(get_db)):
    offer = db.get(Offer, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(offer, key, value)
    if any(k in data for k in ("title", "company", "location")):
        offer.content_hash = compute_content_hash(
            offer.title, offer.company, offer.location
        )
    db.commit()
    db.refresh(offer)
    return offer


@router.delete("/{offer_id}", status_code=204)
def delete_offer(offer_id: uuid.UUID, db: Session = Depends(get_db)):
    offer = db.get(Offer, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    db.delete(offer)
    db.commit()


@router.get("/{offer_id}", response_model=OfferRead)
def get_offer_detail(offer_id: uuid.UUID, db: Session = Depends(get_db)):
    stmt = (
        select(Offer)
        .options(joinedload(Offer.source))
        .where(Offer.id == offer_id)
    )
    offer = db.execute(stmt).scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer
