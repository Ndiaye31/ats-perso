import csv
import io
import logging
import re
import unicodedata
from dataclasses import dataclass

import requests

from app.scrapers.base import HEADERS, RawOffer

logger = logging.getLogger(__name__)

DEFAULT_CSP_CSV_URL = (
    "https://www.data.gouv.fr/api/1/datasets/r/"
    "867034a2-2fa1-41b4-bd39-c84691ea618f"
)
DATASET_PAGE_URL = "https://www.data.gouv.fr/datasets/les-offres-diffusees-sur-choisir-le-service-public"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)


@dataclass
class ImportStats:
    total_rows: int = 0
    kept_email: int = 0
    skipped_non_email: int = 0
    skipped_missing_email: int = 0


class ChoisirLeServicePublicCsvImporter:
    source_name = "choisirleservicepublic.gouv.fr"
    source_url = "https://choisirleservicepublic.gouv.fr"

    def __init__(self, csv_url: str = DEFAULT_CSP_CSV_URL, timeout: int = 30):
        self.csv_url = csv_url
        self.timeout = timeout

    def fetch_offers(self) -> tuple[list[RawOffer], dict]:
        csv_url = self._resolve_csv_url()
        response = requests.get(csv_url, headers=HEADERS, timeout=self.timeout)
        response.raise_for_status()
        return self.parse_csv_text(response.content.decode("utf-8-sig", errors="replace"))

    def _resolve_csv_url(self) -> str:
        try:
            response = requests.get(DATASET_PAGE_URL, headers=HEADERS, timeout=self.timeout)
            response.raise_for_status()
            matches = re.findall(
                r"https://www\.data\.gouv\.fr/api/1/datasets/r/[0-9a-f-]+",
                response.text,
                flags=re.IGNORECASE,
            )
            if matches:
                return matches[0]
        except requests.RequestException as exc:
            logger.warning("[CSP CSV] Page data.gouv indisponible, fallback ressource statique: %s", exc)
        return self.csv_url

    def parse_csv_text(self, csv_text: str) -> tuple[list[RawOffer], dict]:
        reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
        offers: list[RawOffer] = []
        stats = ImportStats()

        for row in reader:
            stats.total_rows += 1
            normalized = {self._normalize_key(k): (v or "").strip() for k, v in row.items() if k}
            mode = self._detect_apply_mode(normalized)
            if mode != "email":
                stats.skipped_non_email += 1
                continue

            email = self._extract_email(normalized)
            if not email:
                stats.skipped_missing_email += 1
                continue

            title = self._pick(
                normalized,
                "intitule",
                "intitule_du_poste",
                "titre",
                "libelle",
            )
            company = self._pick(
                normalized,
                "employeur",
                "organisme_de_rattachement",
                "organisme",
                "ministere",
                "nom_employeur",
                "structure",
            )
            if not title or not company:
                stats.skipped_missing_email += 1
                continue

            offers.append(
                RawOffer(
                    title=title,
                    company=company,
                    location=self._pick(
                        normalized,
                        "lieu_d_affectation",
                        "localisation_du_poste",
                        "lieu_affectation",
                        "localisation",
                        "ville",
                        "commune",
                    ),
                    url=self._pick(
                        normalized,
                        "url",
                        "url_offre",
                        "lien",
                        "lien_offre",
                        "permalien",
                    ),
                    description=self._build_description(normalized),
                    date_limite=self._pick(
                        normalized,
                        "date_limite",
                        "date_limite_candidature",
                        "date_de_fin_de_publication_par_defaut",
                        "date_de_fin_de_publication",
                    ),
                    email_contact=email,
                    candidature_url=None,
                )
            )
            stats.kept_email += 1

        return offers, {
            "total_rows": stats.total_rows,
            "kept_email": stats.kept_email,
            "skipped_non_email": stats.skipped_non_email,
            "skipped_missing_email": stats.skipped_missing_email,
        }

    def _detect_apply_mode(self, row: dict[str, str]) -> str:
        values = " ".join(v for v in row.values() if v).lower()

        if "mailto:" in values or EMAIL_RE.search(values):
            return "email"
        if any(token in values for token in ("candidater en ligne", "en ligne", "formulaire")):
            return "plateforme"
        if any(token in values for token in ("portail", "redir", "site employeur", "site de l'employeur")):
            return "portail_tiers"
        return "email" if self._extract_email(row) else "inconnu"

    def _extract_email(self, row: dict[str, str]) -> str | None:
        preferred_keys = (
            "email",
            "courriel",
            "mail",
            "contact_email",
            "email_contact",
            "courriel_contact",
            "contact",
            "contact_candidature",
            "modalites_de_candidature",
        )
        values = [row.get(key, "") for key in preferred_keys]
        values.extend(v for k, v in row.items() if k not in preferred_keys)
        for value in values:
            match = EMAIL_RE.search(value)
            if match:
                return match.group(0)
        return None

    def _pick(self, row: dict[str, str], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if value:
                return value
        return None

    def _build_description(self, row: dict[str, str]) -> str | None:
        direct = self._pick(
            row,
            "description",
            "missions",
            "descriptif",
            "resume",
        )
        if direct:
            return direct

        sections = [
            ("Référence", self._pick(row, "reference")),
            ("Versant", self._pick(row, "versant")),
            ("Métier", self._pick(row, "metier")),
            ("Statut du poste", self._pick(row, "statut_du_poste")),
            ("Nature de l'emploi", self._pick(row, "nature_de_l_emploi")),
            ("Nature de contrat", self._pick(row, "nature_de_contrat")),
            ("Durée du contrat", self._pick(row, "duree_du_contrat")),
            ("Catégorie", self._pick(row, "categorie")),
            ("Employeur", self._pick(row, "employeur", "organisme_de_rattachement")),
            ("Localisation", self._pick(row, "localisation_du_poste")),
            ("Lieu d'affectation", self._pick(row, "lieu_d_affectation")),
            ("Télétravail", self._pick(row, "teletravail")),
            ("Management", self._pick(row, "management")),
            ("Temps plein", self._pick(row, "temps_plein")),
            ("Durée du poste", self._pick(row, "duree_du_poste")),
            ("Niveau d'études", self._pick(row, "niveau_d_etudes")),
            ("Niveau d'expérience", self._pick(row, "niveau_d_experience_min_requis")),
            ("Compétences attendues", self._pick(row, "competences_attendues")),
            ("Documents à transmettre", self._pick(row, "documents_a_transmettre")),
            ("Avis de vacances au JO", self._pick(row, "avis_de_vacances_au_jo")),
        ]
        lines = [f"{label}: {value.strip()}" for label, value in sections if value and value.strip()]
        return "\n".join(lines) if lines else None

    def _normalize_key(self, key: str) -> str:
        key = unicodedata.normalize("NFKD", key).encode("ascii", "ignore").decode("ascii")
        key = key.strip().lower()
        key = re.sub(r"[^a-z0-9]+", "_", key)
        return key.strip("_")
