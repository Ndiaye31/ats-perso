"""Scraper pour emploi-territorial.fr — délègue au BaseScraper config-driven."""
from app.scrapers.base import BaseScraper, RawOffer, load_configs


def fetch_offers(max_pages: int = 2) -> list[RawOffer]:
    """Conservé pour compatibilité. Utilise BaseScraper + scrapers.yml."""
    configs = {c.name: c for c in load_configs()}
    config = configs.get("emploi-territorial.fr")
    if not config:
        return []
    config.max_pages = max_pages
    return BaseScraper(config).fetch_offers()
