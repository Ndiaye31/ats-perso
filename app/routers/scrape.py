import logging
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from requests import RequestException
from sqlalchemy.orm import Session

from app.database import get_db
from app.importers.choisirleservicepublic_csv import ChoisirLeServicePublicCsvImporter
from app.logging_utils import log_event
from app.scrapers.base import BaseScraper, ScraperConfig, load_configs
from app.services.offer_ingestion import ingest_raw_offers, load_known_hashes

router = APIRouter(prefix="/offres", tags=["scraping"])
logger = logging.getLogger(__name__)


@router.post("/scrape")
def scrape_all(db: Session = Depends(get_db)) -> dict:
    """Collecte toutes les sources configurées: scrapers HTML + imports dédiés."""
    start = perf_counter()
    configs = load_configs()
    known_hashes = load_known_hashes(db)
    results = {}
    for config in configs:
        results[config.name] = _scrape_source(db, config, known_hashes)
    results["choisirleservicepublic.gouv.fr"] = _import_choisirleservicepublic(db, known_hashes)
    db.commit()
    log_event(
        logger,
        logging.INFO,
        "scrape_all_completed",
        source="all",
        duration_ms=round((perf_counter() - start) * 1000, 2),
        sources_count=len(configs) + 1,
    )
    return results


@router.post("/scrape/{source_name}")
def scrape_one(source_name: str, db: Session = Depends(get_db)) -> dict:
    """Collecte une source spécifique par son nom."""
    start = perf_counter()
    configs = {c.name: c for c in load_configs()}
    known_hashes = load_known_hashes(db)
    if source_name == "choisirleservicepublic.gouv.fr":
        result = _import_choisirleservicepublic(db, known_hashes)
        db.commit()
        log_event(
            logger,
            logging.INFO,
            "scrape_one_completed",
            source=source_name,
            duration_ms=round((perf_counter() - start) * 1000, 2),
            inserted=result.get("inserted"),
            skipped=result.get("skipped"),
        )
        return result
    if source_name not in configs:
        raise HTTPException(status_code=404, detail=f"Source '{source_name}' introuvable dans scrapers.yml")
    result = _scrape_source(db, configs[source_name], known_hashes)
    db.commit()
    log_event(
        logger,
        logging.INFO,
        "scrape_one_completed",
        source=source_name,
        duration_ms=round((perf_counter() - start) * 1000, 2),
        inserted=result.get("inserted"),
        skipped=result.get("skipped"),
    )
    return result


def _get_scraper(config: ScraperConfig) -> BaseScraper:
    """Retourne le scraper adapté au site (custom ou générique)."""
    return BaseScraper(config)


def _scrape_source(db: Session, config: ScraperConfig, known_hashes: set[str]) -> dict:
    start = perf_counter()
    log_event(logger, logging.INFO, "scrape_source_started", source=config.name)

    t_fetch_start = perf_counter()
    scraper = _get_scraper(config)
    raw_offers = scraper.fetch_offers(known_hashes=known_hashes)
    fetch_seconds = perf_counter() - t_fetch_start

    result = ingest_raw_offers(
        db,
        source_name=config.name,
        source_url=config.base_url,
        raw_offers=raw_offers,
        known_hashes=known_hashes,
    )

    total_seconds = perf_counter() - start
    result["timings"]["fetch_seconds"] = round(fetch_seconds, 3)
    result["timings"]["total_seconds"] = round(total_seconds, 3)
    log_event(
        logger,
        logging.INFO,
        "scrape_source_completed",
        source=config.name,
        duration_ms=round(total_seconds * 1000, 2),
        inserted=result.get("inserted"),
        skipped=result.get("skipped"),
        total_scraped=len(raw_offers),
    )
    return result


def _import_choisirleservicepublic(db: Session, known_hashes: set[str]) -> dict:
    start = perf_counter()
    importer = ChoisirLeServicePublicCsvImporter()
    try:
        raw_offers, import_stats = importer.fetch_offers()
    except RequestException as exc:
        logger.warning("[choisirleservicepublic.gouv.fr] Import CSV impossible: %s", exc)
        return {
            "inserted": 0,
            "skipped": 0,
            "total_scraped": 0,
            "import": {
                "total_rows": 0,
                "kept_email": 0,
                "skipped_non_email": 0,
                "skipped_missing_email": 0,
                "error": str(exc),
            },
            "timings": {
                "fetch_seconds": round(perf_counter() - start, 3),
                "total_seconds": round(perf_counter() - start, 3),
                "insert_seconds": 0.0,
            },
        }
    result = ingest_raw_offers(
        db,
        source_name=importer.source_name,
        source_url=importer.source_url,
        raw_offers=raw_offers,
        known_hashes=known_hashes,
    )
    result["import"] = import_stats
    result["timings"]["fetch_seconds"] = round(perf_counter() - start, 3)
    result["timings"]["total_seconds"] = round(perf_counter() - start, 3)
    return result
