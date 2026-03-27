"""
Scraper éducation — API officielle data.education.gouv.fr
Récupère les établissements scolaires d'Île-de-France pour candidatures spontanées.
Départements ciblés : 77, 93, 94, 91, 75
"""

import logging
import time

import requests
from datetime import datetime

logger = logging.getLogger(__name__)

API_URL = (
    "https://data.education.gouv.fr/api/explore/v2.1"
    "/catalog/datasets/fr-en-annuaire-education/records"
)

# Format à 3 chiffres pour l'API Education
DEPARTEMENTS = ["077", "093", "094", "091", "075"]

# Types d'établissements pertinents (volume admin suffisant)
TYPES_CIBLES = [
    "Lycée",
    "Collège",
    "Lycée professionnel",
    "Lycée polyvalent",
    "Lycée technologique",
    "EREA",
    "SEGPA",
    "CIO",
    "GRETA",
]

POSTES_PAR_TYPE: dict[str, str] = {
    "Lycée":               "Gestionnaire administratif / Assistant de direction",
    "Collège":             "Secrétaire administratif / Assistant d'établissement",
    "Lycée professionnel": "Gestionnaire administratif",
    "Lycée polyvalent":    "Gestionnaire administratif",
    "Lycée technologique": "Gestionnaire administratif",
    "EREA":                "Assistant administratif",
    "SEGPA":               "Assistant administratif",
    "CIO":                 "Assistant administratif / Coordinateur",
    "GRETA":               "Assistant de gestion / Coordinateur administratif",
}

HEADERS = {"User-Agent": "mon-ATS/1.0"}


def _normalize_education_type(type_etab: str) -> str:
    if "GRETA" in type_etab:
        return "greta"
    if "CIO" in type_etab:
        return "cio"
    if "Collège" in type_etab:
        return "college"
    if any(t in type_etab for t in ["Lycée", "EREA", "SEGPA"]):
        return "lycee"
    return ""


def scrape_education() -> list[dict]:
    """
    Récupère les établissements scolaires d'Île-de-France via l'API Education nationale.
    Retourne une liste de dicts compatibles CibleSpontanee.
    """
    offres: list[dict] = []
    seen: set[str] = set()

    for dept in DEPARTEMENTS:
        offset = 0
        limit = 100

        while True:
            time.sleep(3)
            params = {
                "where": f'code_departement="{dept}"',
                "limit": limit,
                "offset": offset,
                "select": (
                    "nom_etablissement,type_etablissement,"
                    "nom_commune,mail,telephone,"
                    "adresse_1,code_postal"
                ),
            }
            try:
                resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(
                    "scraper_education: erreur dept %s offset %d : %s", dept, offset, e
                )
                break

            records = data.get("results", [])
            if not records:
                break

            for r in records:
                nom = (r.get("nom_etablissement") or "").strip()
                type_etab = (r.get("type_etablissement") or "").strip()
                email = (r.get("mail") or "").strip().lower()
                commune = (r.get("nom_commune") or "").strip()
                cp = (r.get("code_postal") or "").strip()

                if not any(t in type_etab for t in TYPES_CIBLES):
                    continue

                uid = f"{nom}|{cp}"
                if uid in seen:
                    continue
                seen.add(uid)

                poste_cible = next(
                    (POSTES_PAR_TYPE[t] for t in TYPES_CIBLES if t in type_etab),
                    "Assistant administratif / Gestionnaire",
                )
                education_type = _normalize_education_type(type_etab)

                offres.append({
                    "nom": f"{nom} ({commune})",
                    "email": email,
                    "departement": dept[-2:],
                    "secteur": "education",
                    "type_organisation": type_etab,
                    "education_type": education_type,
                    "titre_poste": poste_cible,
                    "description": (
                        f"Établissement : {type_etab}\n"
                        f"Commune : {commune} {cp}\n"
                        f"Tél : {r.get('telephone', '')}"
                    ),
                    "date_scrape": datetime.now().isoformat(),
                })

            logger.info(
                "scraper_education: dept %s offset %d — %d établissements",
                dept, offset, len(records),
            )

            if len(records) < limit:
                break
            offset += limit

    # Priorité aux établissements avec email
    offres.sort(key=lambda o: (0 if o["email"] else 1))

    total_email = sum(1 for o in offres if o["email"])
    logger.info(
        "scraper_education: total %d établissements (%d avec email)", len(offres), total_email
    )
    return offres
