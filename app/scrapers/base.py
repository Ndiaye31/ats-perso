"""Scraper générique piloté par config/scrapers.yml.

Ajouter un nouveau site = ajouter un bloc dans scrapers.yml, aucun code à écrire.
"""
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

CONFIG_PATH = Path(__file__).parents[2] / "config" / "scrapers.yml"

logger = logging.getLogger(__name__)


@dataclass
class RawOffer:
    title: str
    company: str
    location: str | None
    url: str | None
    description: str | None
    date_limite: str | None
    email_contact: str | None
    candidature_url: str | None = None


@dataclass
class ScraperConfig:
    name: str
    base_url: str
    search_url: str
    max_pages: int
    fetch_detail: bool
    parse_pdf: bool
    delay: float
    list_selectors: dict
    page_param: str = "page"
    page_start: int = 1
    detail_selectors: dict = field(default_factory=dict)


def load_configs() -> list[ScraperConfig]:
    """Charge la liste des sources depuis config/scrapers.yml."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [
        ScraperConfig(
            name=s["name"],
            base_url=s["base_url"],
            search_url=s["search_url"],
            max_pages=s.get("max_pages", 5),
            fetch_detail=s.get("fetch_detail", False),
            parse_pdf=s.get("parse_pdf", False),
            delay=s.get("delay", 1.0),
            list_selectors=s.get("list_selectors", {}),
            detail_selectors=s.get("detail_selectors", {}),
            page_param=s.get("page_param", "page"),
            page_start=s.get("page_start", 1),
        )
        for s in data.get("sources", [])
        if s.get("type", "html") != "csv"
    ]


def load_csv_configs():
    """Charge les sources CSV depuis config/scrapers.yml."""
    from app.scrapers.csv_importer import CsvImporterConfig

    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [
        CsvImporterConfig(
            name=s["name"],
            csv_url=s["csv_url"],
            separator=s.get("separator", ","),
            columns=s.get("columns", {}),
            dataset_api=s.get("dataset_api"),
            dataset_page=s.get("dataset_page"),
            resource_url_pattern=s.get("resource_url_pattern"),
        )
        for s in data.get("sources", [])
        if s.get("type") == "csv"
    ]


class BaseScraper:
    """Scrape n'importe quel site à partir de sa config YAML."""

    def __init__(self, config: ScraperConfig):
        self.config = config

    def fetch_offers(self, known_hashes: set[str] | None = None) -> list[RawOffer]:
        session = requests.Session()
        session.headers.update(HEADERS)
        offers: list[RawOffer] = []
        seen_hashes = known_hashes if known_hashes is not None else set()
        for i in range(self.config.max_pages):
            page_num = self.config.page_start + i
            page_offers = self._fetch_page(session, page_num, seen_hashes)
            if not page_offers:
                break
            offers.extend(page_offers)
            logger.info("[%s] Page %d : %d offres collectées.", self.config.name, page_num, len(page_offers))
            time.sleep(self.config.delay)
        session.close()
        return offers

    def _fetch_page(self, session: requests.Session, page: int, known_hashes: set[str]) -> list[RawOffer]:
        sel = self.config.list_selectors
        try:
            resp = session.get(
                self.config.search_url,
                params={self.config.page_param: page},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("[%s] Erreur page %d : %s", self.config.name, page, e)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        cards = soup.select(sel.get("cards", "article"))
        if not cards:
            logger.info("[%s] Page %d : aucune carte trouvée, arrêt.", self.config.name, page)
            return []

        offers = []
        for card in cards:
            title = self._extract(card, sel.get("title", "h2, h3"))
            if not title:
                continue

            company = self._extract(card, sel.get("company", "")) or "Inconnu"
            location = self._extract(card, sel.get("location", ""))
            date_limite = self._extract(card, sel.get("date_limite", ""))
            email = self._extract_email(card, sel.get("email", ""))

            href = self._extract_href(card, sel.get("link", "a"))
            url = self._resolve_url(href)

            description = None
            candidature_url = None
            if url and self.config.fetch_detail:
                from app.utils import compute_content_hash

                h = compute_content_hash(title, company, location)
                if h not in known_hashes:
                    time.sleep(self.config.delay)
                    detail = self._fetch_detail(session, url)
                    description = detail.get("description")
                    if not email:
                        email = detail.get("email")
                    candidature_url = detail.get("candidature_url")
                    if not date_limite:
                        date_limite = detail.get("date_limite")
                    known_hashes.add(h)

            offers.append(
                RawOffer(
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description=description,
                    date_limite=date_limite,
                    email_contact=email,
                    candidature_url=candidature_url,
                )
            )

        return offers

    def _fetch_detail(self, session: requests.Session, url: str) -> dict:
        """Visite la page de détail pour extraire description + email + PDFs éventuels."""
        from app.scrapers.pdf_parser import extract_from_pdf

        sel = self.config.detail_selectors
        resp = None
        for attempt in range(3):
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
                break
            except requests.RequestException as e:
                wait = 3 * (attempt + 1)
                logger.warning("[%s] Erreur détail %s (tentative %d/3, retry dans %ds) : %s",
                               self.config.name, url, attempt + 1, wait, e)
                time.sleep(wait)
        if resp is None or not resp.ok:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")

        description = None
        if sel.get("description"):
            el = soup.select_one(sel["description"])
            if el:
                description = el.get_text(separator="\n", strip=True)

        import re, html as html_lib
        email = None
        candidature_url = None
        base_domain = self.config.base_url.replace("https://", "").replace("http://", "").split("/")[0]

        # 1. Lignes label/valeur structurées (.offre-item) — emploi-territorial.fr
        for row in soup.select(".offre-item"):
            label_el = row.select_one(".offre-item-label, .offre-item-text:first-child")
            label = label_el.get_text(strip=True).lower() if label_el else ""
            value_el = row.select_one(".offre-item-value, .offre-item-text:last-child")

            if "lien de candidature" in label and value_el:
                a = value_el.select_one("a[href]")
                if a:
                    href = str(a.get("href", ""))
                    link_domain = href.replace("https://", "").replace("http://", "").split("/")[0]
                    if link_domain != base_domain:
                        candidature_url = href

            if not email and any(kw in label for kw in ("contact", "information", "renseignement")):
                mailto = value_el.select_one("a[href^='mailto:']") if value_el else None
                if mailto:
                    email = mailto["href"].replace("mailto:", "").strip() or None
                elif value_el:
                    match = re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", value_el.get_text())
                    if match:
                        email = match.group()

        # 2. Décodage Cloudflare email protection — emploi.fhf.fr et autres
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

        # 3. URL externe dans div.contact — emploi.fhf.fr
        if not candidature_url:
            contact_div = soup.select_one("div.contact")
            if contact_div:
                matches = re.findall(r"https?://[^\s<>\"']+", contact_div.decode_contents())
                for u in matches:
                    u = html_lib.unescape(u).rstrip(".,;)")
                    domain = u.replace("https://", "").replace("http://", "").split("/")[0]
                    if domain != base_domain:
                        candidature_url = u
                        break

        # 4. Fallback global : mailto visible
        if not email:
            mailto = soup.select_one("a[href^='mailto:']")
            if mailto:
                email = mailto["href"].replace("mailto:", "").strip() or None

        # Extraction PDF si activée pour ce site et aucun email trouvé en HTML
        if self.config.parse_pdf and not email:
            pdf_links = [
                self._resolve_url(a["href"])
                for a in soup.select("a[href$='.pdf']")
                if a.get("href")
            ]
            for pdf_url in pdf_links:
                time.sleep(self.config.delay)
                result = extract_from_pdf(pdf_url, HEADERS)
                if result["emails"]:
                    email = result["emails"][0]
                if not description and result["text"]:
                    description = result["text"]
                if email:
                    break

        # 5. Date limite de candidature — emploi-territorial.fr (.offre-item)
        date_limite = None
        for row in soup.select(".offre-item"):
            label_el = row.select_one(".offre-item-label, .offre-item-text:first-child")
            label = label_el.get_text(strip=True).lower() if label_el else ""
            if "date limite" in label:
                value_el = row.select_one(".offre-item-value, .offre-item-text:last-child")
                if value_el:
                    raw = value_el.get_text(strip=True)
                    m = re.search(r"(\d{2}/\d{2}/\d{4})", raw)
                    if m:
                        date_limite = m.group(1)
                break

        return {"description": description, "email": email, "candidature_url": candidature_url, "date_limite": date_limite}

    # ── helpers ──────────────────────────────────────────────────────────────

    def _extract(self, tag, selector: str) -> str | None:
        if not selector:
            return None
        el = tag.select_one(selector)
        return el.get_text(strip=True) if el else None

    def _extract_href(self, tag, selector: str) -> str | None:
        if not selector:
            return None
        if tag.name == "a":
            return tag.get("href")
        link = tag.select_one(selector)
        return link.get("href") if link else None

    def _extract_email(self, tag, selector: str) -> str | None:
        if not selector:
            return None
        el = tag.select_one(selector)
        if not el:
            return None
        href = el.get("href", "")
        return href.replace("mailto:", "").strip() or el.get_text(strip=True) or None

    def _resolve_url(self, href: str | None) -> str | None:
        if not href:
            return None
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"{self.config.base_url}{href}"
        return href
