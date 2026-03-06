import uuid
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.offer import Offer
from app.models.source import Source
from app.profil import profil
from app.scoring import MIN_SCORE, score_offer
from app.scrapers.base import BaseScraper, ScraperConfig, load_configs
from app.utils import compute_content_hash

router = APIRouter(prefix="/offres", tags=["scraping"])


def _load_known_hashes(db: Session) -> set[str]:
    """Charge tous les hashes d'offres existantes pour éviter de re-scraper les détails."""
    rows = db.query(Offer.content_hash).filter(Offer.content_hash.isnot(None)).all()
    return {h for (h,) in rows}


@router.post("/scrape")
def scrape_all(db: Session = Depends(get_db)) -> dict:
    """Scrape tous les sites configurés dans config/scrapers.yml."""
    configs = load_configs()
    known_hashes = _load_known_hashes(db)
    results = {}
    for config in configs:
        results[config.name] = _scrape_source(db, config, known_hashes)
    db.commit()
    return results


@router.post("/scrape/{source_name}")
def scrape_one(source_name: str, db: Session = Depends(get_db)) -> dict:
    """Scrape un site spécifique par son nom (ex: emploi-territorial.fr)."""
    configs = {c.name: c for c in load_configs()}
    if source_name not in configs:
        raise HTTPException(status_code=404, detail=f"Source '{source_name}' introuvable dans scrapers.yml")
    known_hashes = _load_known_hashes(db)
    result = _scrape_source(db, configs[source_name], known_hashes)
    db.commit()
    return result


def _scrape_source(db: Session, config: ScraperConfig, known_hashes: set[str]) -> dict:
    start = perf_counter()
    source = db.query(Source).filter_by(name=config.name).first()
    if not source:
        source = Source(id=uuid.uuid4(), name=config.name, url=config.base_url)
        db.add(source)
        db.flush()

    t_fetch_start = perf_counter()
    raw_offers = BaseScraper(config).fetch_offers(known_hashes=known_hashes)
    fetch_seconds = perf_counter() - t_fetch_start

    inserted = skipped = 0
    rows_to_insert = []

    for raw in raw_offers:
        h = compute_content_hash(raw.title, raw.company, raw.location)
        if h in known_hashes:
            skipped += 1
            continue

        offer = Offer(
            id=uuid.uuid4(),
            title=raw.title,
            company=raw.company,
            location=raw.location,
            url=raw.url,
            description=raw.description,
            date_limite=raw.date_limite,
            contact_email=raw.email_contact,
            candidature_url=raw.candidature_url,
            status="new",
            content_hash=h,
            source_id=source.id,
        )
        s, details = score_offer(offer, profil)
        if s < MIN_SCORE:
            skipped += 1
            continue

        offer.score = s
        offer.score_details = details
        rows_to_insert.append(
            {
                "id": offer.id,
                "title": offer.title,
                "company": offer.company,
                "location": offer.location,
                "url": offer.url,
                "description": offer.description,
                "date_limite": offer.date_limite,
                "contact_email": offer.contact_email,
                "candidature_url": offer.candidature_url,
                "status": offer.status,
                "content_hash": offer.content_hash,
                "source_id": offer.source_id,
                "score": offer.score,
                "score_details": offer.score_details,
            }
        )
        known_hashes.add(h)

    t_insert_start = perf_counter()
    if rows_to_insert:
        stmt = (
            pg_insert(Offer.__table__)
            .values(rows_to_insert)
            .on_conflict_do_nothing(index_elements=["content_hash"])
            .returning(Offer.content_hash)
        )
        inserted_hashes = [row[0] for row in db.execute(stmt).all()]
        inserted = len(inserted_hashes)
        skipped += len(rows_to_insert) - inserted
        known_hashes.update(inserted_hashes)
    insert_seconds = perf_counter() - t_insert_start

    total_seconds = perf_counter() - start
    return {
        "inserted": inserted,
        "skipped": skipped,
        "total_scraped": len(raw_offers),
        "timings": {
            "fetch_seconds": round(fetch_seconds, 3),
            "insert_seconds": round(insert_seconds, 3),
            "total_seconds": round(total_seconds, 3),
        },
    }
