import logging
import uuid
from time import perf_counter

from sqlalchemy import insert as sa_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.offer import Offer
from app.models.source import Source
from app.profil import profil
from app.scoring import MIN_SCORE, score_offer
from app.scrapers.base import RawOffer
from app.utils import compute_content_hash

logger = logging.getLogger(__name__)


def load_known_hashes(db: Session) -> set[str]:
    rows = db.query(Offer.content_hash).filter(Offer.content_hash.isnot(None)).all()
    return {h for (h,) in rows}


def get_or_create_source(db: Session, *, name: str, url: str | None) -> Source:
    source = db.query(Source).filter_by(name=name).first()
    if source:
        return source
    source = Source(id=uuid.uuid4(), name=name, url=url)
    db.add(source)
    db.flush()
    return source


def ingest_raw_offers(
    db: Session,
    *,
    source_name: str,
    source_url: str | None,
    raw_offers: list[RawOffer],
    known_hashes: set[str] | None = None,
) -> dict:
    start = perf_counter()
    source = get_or_create_source(db, name=source_name, url=source_url)
    seen_hashes = known_hashes if known_hashes is not None else load_known_hashes(db)

    inserted = 0
    skipped = 0
    updated = 0
    rows_to_insert = []

    for raw in raw_offers:
        h = compute_content_hash(raw.title, raw.company, raw.location)
        if h in seen_hashes:
            existing = db.query(Offer).filter_by(content_hash=h).first()
            if existing and _enrich_existing_offer(existing, raw):
                updated += 1
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
        if not raw.email_contact and not raw.candidature_url:
            skipped += 1
            continue

        score, details = score_offer(offer, profil)
        if score < MIN_SCORE:
            skipped += 1
            continue

        offer.score = score
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
        seen_hashes.add(h)

    insert_start = perf_counter()
    if rows_to_insert:
        if db.bind and db.bind.dialect.name == "postgresql":
            stmt = (
                pg_insert(Offer.__table__)
                .values(rows_to_insert)
                .on_conflict_do_nothing(index_elements=["content_hash"])
                .returning(Offer.content_hash)
            )
            inserted_hashes = [row[0] for row in db.execute(stmt).all()]
            inserted = len(inserted_hashes)
            seen_hashes.update(inserted_hashes)
        else:
            inserted_hashes = []
            for row in rows_to_insert:
                stmt = sa_insert(Offer.__table__).values(row)
                try:
                    db.execute(stmt)
                    inserted += 1
                    inserted_hashes.append(row["content_hash"])
                except Exception:
                    skipped += 1
            seen_hashes.update(inserted_hashes)
        skipped += len(rows_to_insert) - inserted

    result = {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total_scraped": len(raw_offers),
        "timings": {
            "insert_seconds": round(perf_counter() - insert_start, 3),
            "total_seconds": round(perf_counter() - start, 3),
        },
    }
    logger.info(
        "[%s] Ingestion terminée: inserted=%s skipped=%s total=%s",
        source_name,
        inserted,
        skipped,
        len(raw_offers),
    )
    return result


def _enrich_existing_offer(existing: Offer, raw: RawOffer) -> bool:
    changed = False
    updates = {
        "description": raw.description,
        "url": raw.url,
        "date_limite": raw.date_limite,
        "contact_email": raw.email_contact,
        "candidature_url": raw.candidature_url,
    }
    for field, incoming in updates.items():
        current = getattr(existing, field)
        if incoming and (not current or len(str(incoming)) > len(str(current))):
            setattr(existing, field, incoming)
            changed = True
    return changed
