import logging
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.logging_utils import log_event
from app.scrapers.base import BaseScraper, ScraperConfig, load_configs, load_csv_configs
from app.scrapers.csv_importer import CsvImporter, CsvImporterConfig
from app.services.offer_ingestion import ingest_raw_offers, load_known_hashes

router = APIRouter(prefix="/offres", tags=["scraping"])
logger = logging.getLogger(__name__)


@router.post("/scrape")
def scrape_all(db: Session = Depends(get_db)) -> dict:
    """Collecte toutes les sources configurées: scrapers HTML + imports CSV."""
    start = perf_counter()
    configs = load_configs()
    known_hashes = load_known_hashes(db)
    results = {}
    for config in configs:
        results[config.name] = _scrape_source(db, config, known_hashes)
    for csv_config in load_csv_configs():
        results[csv_config.name] = _import_csv_source(db, csv_config, known_hashes)
    db.commit()
    log_event(
        logger,
        logging.INFO,
        "scrape_all_completed",
        source="all",
        duration_ms=round((perf_counter() - start) * 1000, 2),
        sources_count=len(configs) + len(load_csv_configs()),
    )
    return results


@router.post("/scrape/{source_name}")
def scrape_one(source_name: str, db: Session = Depends(get_db)) -> dict:
    """Collecte une source spécifique par son nom."""
    start = perf_counter()
    known_hashes = load_known_hashes(db)

    # Check HTML configs
    configs = {c.name: c for c in load_configs()}
    if source_name in configs:
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

    # Check CSV configs
    csv_configs = {c.name: c for c in load_csv_configs()}
    if source_name in csv_configs:
        result = _import_csv_source(db, csv_configs[source_name], known_hashes)
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

    raise HTTPException(status_code=404, detail=f"Source '{source_name}' introuvable dans scrapers.yml")


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


def _import_csv_source(db: Session, config: CsvImporterConfig, known_hashes: set[str]) -> dict:
    start = perf_counter()
    log_event(logger, logging.INFO, "csv_import_started", source=config.name)

    importer = CsvImporter(config)
    t_fetch_start = perf_counter()
    raw_offers = importer.fetch_offers(known_hashes=known_hashes)
    fetch_seconds = perf_counter() - t_fetch_start

    result = ingest_raw_offers(
        db,
        source_name=config.name,
        source_url=config.csv_url,
        raw_offers=raw_offers,
        known_hashes=known_hashes,
    )

    total_seconds = perf_counter() - start
    result["timings"]["fetch_seconds"] = round(fetch_seconds, 3)
    result["timings"]["total_seconds"] = round(total_seconds, 3)
    log_event(
        logger,
        logging.INFO,
        "csv_import_completed",
        source=config.name,
        duration_ms=round(total_seconds * 1000, 2),
        inserted=result.get("inserted"),
        skipped=result.get("skipped"),
        total_scraped=len(raw_offers),
    )
    return result
