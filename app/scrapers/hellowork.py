"""Scraper pour hellowork.com.

Sous-classe de BaseScraper — override _fetch_page (cards sans classes CSS)
et _fetch_detail (extraction JSON-LD JobPosting au lieu de sélecteurs CSS).

Le champ `directApply` du JSON-LD détermine si l'offre est candidate-able
directement sur HelloWork (mode plateforme) ou redirigée vers un portail
tiers (candidature_url renseigné → mode portail_tiers).
"""
import json
import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup, Tag

from app.scrapers.base import BaseScraper, HEADERS, RawOffer

logger = logging.getLogger(__name__)


class HelloWorkScraper(BaseScraper):
    """Scraper HelloWork avec extraction JSON-LD."""

    def _get_session(self) -> requests.Session:
        """Crée une session HTTP, avec fallback cloudscraper si disponible."""
        session = requests.Session()
        session.headers.update(HEADERS)
        return session

    def _request_with_fallback(self, session: requests.Session, url: str,
                                params: dict | None = None, timeout: int = 15) -> requests.Response | None:
        """GET avec fallback cloudscraper en cas de 403."""
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code == 403:
                logger.warning("[hellowork] 403 reçu, tentative avec cloudscraper…")
                try:
                    import cloudscraper
                    scraper = cloudscraper.create_scraper()
                    resp = scraper.get(url, params=params, timeout=timeout)
                except ImportError:
                    logger.warning("[hellowork] cloudscraper non installé, impossible de contourner le 403")
                    return None
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning("[hellowork] Erreur requête %s : %s", url, e)
            return None

    def _fetch_page(self, session: requests.Session, page: int, known_hashes: set[str]) -> list[RawOffer]:
        import time
        from app.utils import compute_content_hash

        resp = self._request_with_fallback(
            session,
            self.config.search_url,
            params={self.config.page_param: page},
        )
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Les cards HelloWork : <a href="/fr-fr/emplois/{id}.html"><h3>Titre</h3></a>
        # suivis de <div> siblings pour entreprise, lieu, contrat, salaire.
        links = soup.select("a[href*='/fr-fr/emplois/']")
        if not links:
            logger.info("[hellowork] Page %d : aucune offre trouvée, arrêt.", page)
            return []

        offers: list[RawOffer] = []
        seen_urls: set[str] = set()

        for link in links:
            href = link.get("href", "")
            if not href or not re.search(r"/emplois/\d+\.html", href):
                continue

            url = href if href.startswith("http") else f"{self.config.base_url}{href}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Titre depuis <h3> dans le lien
            h3 = link.find("h3")
            title = h3.get_text(strip=True) if h3 else link.get_text(strip=True)
            if not title:
                continue

            # Entreprise et lieu : <div> siblings après le lien
            company = "Inconnu"
            location = None
            parent = link.parent
            if parent and isinstance(parent, Tag):
                divs = [d for d in parent.find_all("div", recursive=False)
                        if d.get_text(strip=True)]
                # Structure typique : [image_container], company, location, contrat, salaire
                texts = [d.get_text(strip=True) for d in divs
                         if not d.find("img") and d.get_text(strip=True)]
                if len(texts) >= 1:
                    company = texts[0]
                if len(texts) >= 2:
                    location = texts[1]

            # Déduplication rapide avant de fetch le détail
            h = compute_content_hash(title, company, location)
            if h in known_hashes:
                continue

            # Fetch détail si configuré
            description = None
            date_limite = None
            email_contact = None
            candidature_url = None

            if self.config.fetch_detail:
                time.sleep(self.config.delay)
                detail = self._fetch_detail_jsonld(session, url)
                if detail:
                    description = detail.get("description")
                    date_limite = detail.get("date_limite")
                    email_contact = detail.get("email")
                    candidature_url = detail.get("candidature_url")
                    # Fallbacks depuis JSON-LD
                    if company == "Inconnu" and detail.get("company"):
                        company = detail["company"]
                    if not location and detail.get("location"):
                        location = detail["location"]
                known_hashes.add(h)

            offers.append(RawOffer(
                title=title,
                company=company,
                location=location,
                url=url,
                description=description,
                date_limite=date_limite,
                email_contact=email_contact,
                candidature_url=candidature_url,
            ))

        return offers

    def _fetch_detail_jsonld(self, session: requests.Session, url: str) -> dict | None:
        """Extrait les métadonnées d'une offre HelloWork via JSON-LD JobPosting."""
        resp = self._request_with_fallback(session, url, timeout=20)
        if not resp:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Chercher le JSON-LD JobPosting
        job_posting = None
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    job_posting = data
                    break
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") == "JobPosting":
                            job_posting = item
                            break
                    if job_posting:
                        break
            except (json.JSONDecodeError, TypeError):
                continue

        if not job_posting:
            logger.warning("[hellowork] Pas de JSON-LD JobPosting sur %s", url)
            # Fallback : extraction basique
            return self._fetch_detail_fallback(soup, url)

        result: dict = {}

        # Description (HTML → texte brut)
        raw_desc = job_posting.get("description", "")
        if raw_desc:
            desc_soup = BeautifulSoup(raw_desc, "html.parser")
            result["description"] = desc_soup.get_text(separator="\n", strip=True)

        # Entreprise
        hiring_org = job_posting.get("hiringOrganization")
        if isinstance(hiring_org, dict):
            result["company"] = hiring_org.get("name")

        # Localisation
        job_location = job_posting.get("jobLocation")
        if isinstance(job_location, dict):
            address = job_location.get("address", {})
            if isinstance(address, dict):
                city = address.get("addressLocality", "")
                postal = address.get("postalCode", "")
                result["location"] = f"{city} - {postal[:2]}" if city and postal else city or None

        # Date limite (validThrough → dd/mm/yyyy)
        valid_through = job_posting.get("validThrough")
        if valid_through:
            try:
                dt = datetime.fromisoformat(valid_through.replace("Z", "+00:00"))
                result["date_limite"] = dt.strftime("%d/%m/%Y")
            except (ValueError, TypeError):
                pass

        # directApply : si false, c'est un portail tiers
        direct_apply = job_posting.get("directApply")
        if direct_apply is False:
            result["candidature_url"] = url

        # Email : chercher dans la page HTML (pas dans JSON-LD)
        email = self._extract_email_from_soup(soup)
        if email:
            result["email"] = email

        return result

    def _fetch_detail_fallback(self, soup: BeautifulSoup, url: str) -> dict:
        """Extraction basique si pas de JSON-LD."""
        result: dict = {}

        # Description depuis le contenu principal
        for sel in ("article", "main", ".job-description"):
            el = soup.select_one(sel)
            if el:
                result["description"] = el.get_text(separator="\n", strip=True)
                break

        email = self._extract_email_from_soup(soup)
        if email:
            result["email"] = email

        return result

    def _extract_email_from_soup(self, soup: BeautifulSoup) -> str | None:
        """Extrait un email depuis la page (mailto ou regex)."""
        mailto = soup.select_one("a[href^='mailto:']")
        if mailto:
            email = mailto["href"].replace("mailto:", "").strip()
            if email:
                return email
        # Regex fallback dans le body
        text = soup.get_text()
        match = re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", text)
        return match.group() if match else None

    # Override _fetch_detail pour que le parent BaseScraper ne soit pas appelé
    def _fetch_detail(self, session: requests.Session, url: str) -> dict:
        return self._fetch_detail_jsonld(session, url) or {}
