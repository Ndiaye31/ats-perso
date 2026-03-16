"""Import générique d'offres depuis un CSV distant, piloté par config/scrapers.yml.

Ajouter un nouveau CSV = ajouter un bloc type: csv dans scrapers.yml.
"""

import csv
import io
import logging
import re
from dataclasses import dataclass, field

import requests

from app.scrapers.base import HEADERS, RawOffer
from app.utils import compute_content_hash

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.IGNORECASE)
CSP_OFFER_URL = "https://choisirleservicepublic.gouv.fr/offre-emploi/{ref}/"


@dataclass
class CsvImporterConfig:
    name: str                                    # "choisirleservicepublic.gouv.fr"
    csv_url: str                                 # URL data.gouv.fr du CSV (fallback)
    separator: str = ";"
    columns: dict = field(default_factory=dict)  # mapping logique → nom colonne CSV
    dataset_api: str | None = None               # URL API JSON data.gouv.fr (résolution dynamique)
    dataset_page: str | None = None              # conservé pour compatibilité (non utilisé)
    resource_url_pattern: str | None = None      # conservé pour compatibilité (non utilisé)


class CsvImporter:
    def __init__(self, config: CsvImporterConfig):
        self.config = config

    def fetch_offers(self, known_hashes: set[str] | None = None) -> list[RawOffer]:
        """Télécharge le CSV et retourne les RawOffer."""
        text = self._download_csv()
        if text is None:
            return []
        hashes = known_hashes if known_hashes is not None else set()
        return self._parse_csv(text, hashes)

    def _resolve_csv_url(self) -> str:
        """Résout l'URL du CSV le plus récent via l'API JSON data.gouv.fr.

        data.gouv.fr est une SPA — scraper le HTML ne fonctionne pas.
        L'API retourne la liste des ressources avec leur URL directe et leur date.
        Fallback sur csv_url si l'API est indisponible.
        """
        if not self.config.dataset_api:
            return self.config.csv_url
        try:
            resp = requests.get(self.config.dataset_api, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            # Filtrer les ressources CSV et prendre la plus récente
            csv_resources = [
                r for r in data.get("resources", [])
                if (r.get("format") or "").lower() == "csv" and r.get("url")
            ]
            if csv_resources:
                latest = max(csv_resources, key=lambda r: r.get("last_modified") or "")
                url = latest["url"]
                logger.info("[%s] URL CSV résolue via API: %s", self.config.name, url)
                return url
            logger.warning("[%s] Aucune ressource CSV trouvée via API, fallback sur csv_url", self.config.name)
        except Exception as exc:
            logger.warning("[%s] API data.gouv.fr inaccessible, fallback sur csv_url: %s", self.config.name, exc)
        return self.config.csv_url

    def _download_csv(self) -> str | None:
        """Résout l'URL puis GET, timeout 120s, retourne le texte brut."""
        csv_url = self._resolve_csv_url()
        try:
            resp = requests.get(
                csv_url,
                headers=HEADERS,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.content.decode("utf-8-sig", errors="replace")
        except requests.RequestException as exc:
            logger.warning("[%s] Téléchargement CSV impossible: %s", self.config.name, exc)
            return None

    def _parse_csv(self, text: str, known_hashes: set[str]) -> list[RawOffer]:
        """csv.DictReader(delimiter=';') → RawOffer pour chaque ligne valide."""
        cols = self.config.columns
        reader = csv.DictReader(io.StringIO(text), delimiter=self.config.separator)
        offers: list[RawOffer] = []
        # Set local pour dédupliquer au sein du CSV sans polluer known_hashes.
        # Si on modifiait known_hashes directement, ingest_raw_offers verrait les
        # hashes comme "déjà en base" alors qu'ils n'y sont pas encore → inserted=0.
        seen_in_csv: set[str] = set()

        col_title = cols.get("title", "Intitulé du poste")
        col_company = cols.get("company", "Employeur")
        col_company_fb = cols.get("company_fallback", "Organisme de rattachement")
        col_location = cols.get("location", "Localisation du poste")
        col_reference = cols.get("reference", "Référence")
        col_description = cols.get("description", "Compétences attendues")
        col_date_limite = cols.get("date_limite", "Date de fin de publication par défaut")

        for row in reader:
            title = (row.get(col_title) or "").strip()
            if not title:
                continue

            company = (row.get(col_company) or "").strip()
            if not company:
                company = (row.get(col_company_fb) or "").strip()
            if not company:
                company = "Inconnu"

            location = (row.get(col_location) or "").strip() or None
            ref = (row.get(col_reference) or "").strip()
            url = CSP_OFFER_URL.format(ref=ref) if ref else None
            description = (row.get(col_description) or "").strip() or None
            date_limite = (row.get(col_date_limite) or "").strip() or None

            # Extract email from description (best-effort)
            email = None
            if description:
                match = EMAIL_RE.search(description)
                if match:
                    email = match.group(0)

            # Fallback: scan all columns for email
            if not email:
                for value in row.values():
                    if value:
                        match = EMAIL_RE.search(value)
                        if match:
                            email = match.group(0)
                            break

            # Skip if no email and no URL (can't apply)
            candidature_url = url  # page CSP pour candidature manuelle

            # Dedup via content hash
            h = compute_content_hash(title, company, location)
            if h in known_hashes or h in seen_in_csv:
                continue
            seen_in_csv.add(h)

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

        logger.info("[%s] CSV parsé: %d offres extraites", self.config.name, len(offers))
        return offers
