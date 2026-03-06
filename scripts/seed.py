"""Insert 5 fake offers into the database for testing."""
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.offer import Offer
from app.models.source import Source
from app.utils import compute_content_hash

FAKE_SOURCE = {"name": "LinkedIn", "url": "https://www.linkedin.com/jobs"}

FAKE_OFFERS = [
    {
        "title": "Développeur Backend Python",
        "company": "Doctolib",
        "location": "Paris, France",
        "url": "https://example.com/jobs/1",
        "status": "new",
        "applied_at": None,
    },
    {
        "title": "Ingénieur FastAPI / PostgreSQL",
        "company": "Leboncoin",
        "location": "Paris, France",
        "url": "https://example.com/jobs/2",
        "status": "applied",
        "applied_at": date.today() - timedelta(days=3),
    },
    {
        "title": "Software Engineer – Data Platform",
        "company": "Contentsquare",
        "location": "Remote",
        "url": "https://example.com/jobs/3",
        "status": "interview",
        "applied_at": date.today() - timedelta(days=7),
    },
    {
        "title": "Backend Engineer (Python/Django)",
        "company": "Qonto",
        "location": "Paris, France",
        "url": "https://example.com/jobs/4",
        "status": "new",
        "applied_at": None,
    },
    {
        "title": "Développeur Python Senior",
        "company": "ManoMano",
        "location": "Bordeaux, France",
        "url": "https://example.com/jobs/5",
        "status": "rejected",
        "applied_at": date.today() - timedelta(days=14),
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        # Upsert source
        source = db.query(Source).filter_by(name=FAKE_SOURCE["name"]).first()
        if not source:
            source = Source(id=uuid.uuid4(), **FAKE_SOURCE)
            db.add(source)
            db.flush()
            print(f"Source créée : {source.name}")
        else:
            print(f"Source existante : {source.name}")

        # Insert offers (skip duplicates)
        inserted = skipped = 0
        for data in FAKE_OFFERS:
            h = compute_content_hash(data["title"], data["company"], data.get("location"))
            if db.query(Offer).filter_by(content_hash=h).first():
                print(f"  ~ doublon ignoré : {data['title']} @ {data['company']}")
                skipped += 1
                continue
            offer = Offer(id=uuid.uuid4(), source_id=source.id, content_hash=h, **data)
            db.add(offer)
            inserted += 1
            print(f"  + {offer.title} @ {offer.company}")

        db.commit()
        print(f"\n{inserted} offres insérées, {skipped} doublons ignorés.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
