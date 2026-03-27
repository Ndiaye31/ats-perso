"""
Scraper mairies — API DILA (api-lannuaire.service-public.fr)
Source officielle du gouvernement : emails réels des secrétariats de mairie.
Départements ciblés : 77, 93, 94, 91, 75 (Île-de-France)
"""

import json
import logging
import time

import requests
from datetime import datetime

logger = logging.getLogger(__name__)

API_URL = (
    "https://api-lannuaire.service-public.fr/api/explore/v2.1"
    "/catalog/datasets/api-lannuaire-administration/records"
)

DEPARTEMENTS = ["77", "93", "94", "91", "75"]

TITRE_SPONTANE = "Assistant(e) Administratif(ve) — Candidature Spontanée"

HEADERS = {"User-Agent": "mon-ATS/1.0"}


def _fetch_dept(dept: str) -> list[dict]:
    """Récupère toutes les mairies d'un département avec pagination."""
    results = []
    limit = 100
    offset = 0

    while True:
        try:
            resp = requests.get(
                API_URL,
                params={
                    "where": f'search(pivot, "mairie") AND search(pivot, "{dept}")',
                    "select": "nom,adresse_courriel,telephone,site_internet,pivot",
                    "limit": limit,
                    "offset": offset,
                },
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("scraper_mairies: erreur dept %s offset %d : %s", dept, offset, e)
            break

        batch = data.get("results", [])
        if not batch:
            break

        results.extend(batch)

        if len(batch) < limit:
            break
        offset += limit
        time.sleep(1)

    return results


def _extraire_email(rec: dict) -> str:
    raw = rec.get("adresse_courriel") or ""
    if not raw:
        return ""
    if isinstance(raw, str) and (raw.startswith("[") or raw.startswith("{")):
        try:
            items = json.loads(raw)
            if isinstance(items, dict):
                items = [items]
            for item in items:
                if not isinstance(item, dict):
                    continue
                for key in ("valeur", "adresse_courriel", "email", "value"):
                    val = item.get(key, "")
                    if isinstance(val, str) and "@" in val:
                        return val.strip().lower()
        except Exception:
            pass
    if "@" in raw:
        return raw.strip().lower()
    return ""


def _extraire_telephone(rec: dict) -> str:
    raw = rec.get("telephone") or ""
    if not raw:
        return ""
    if raw.startswith("["):
        try:
            items = json.loads(raw)
            for item in items:
                val = item.get("valeur", "")
                if val:
                    return val.strip()
        except Exception:
            pass
    return raw.strip()


def _extraire_site(rec: dict) -> str:
    raw = rec.get("site_internet") or ""
    if not raw:
        return ""
    if raw.startswith("["):
        try:
            items = json.loads(raw)
            for item in items:
                val = item.get("valeur", "")
                if val and val.startswith("http"):
                    return val.strip()
        except Exception:
            pass
    return raw.strip()


def _code_insee(rec: dict) -> str:
    raw = rec.get("pivot") or "[]"
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
        for item in items:
            codes = item.get("code_insee_commune", [])
            if codes:
                return codes[0]
    except Exception:
        pass
    return ""


def scrape_mairies() -> list[dict]:
    """
    Récupère les mairies d'Île-de-France avec leurs emails via l'API DILA.
    Retourne une liste de dicts compatibles CibleSpontanee.
    """
    offres: list[dict] = []
    seen: set[str] = set()

    for dept in DEPARTEMENTS:
        records = _fetch_dept(dept)
        dept_count = 0

        for rec in records:
            nom_raw = rec.get("nom", "").strip()
            nom = nom_raw.replace("Mairie - ", "").replace("Mairie de ", "").strip()
            if not nom:
                continue

            code = _code_insee(rec)
            uid = code or f"{nom}|{dept}"
            if uid in seen:
                continue
            seen.add(uid)

            email = _extraire_email(rec)
            telephone = _extraire_telephone(rec)
            site = _extraire_site(rec)

            description = (
                f"Candidature spontanée — poste administratif en mairie.\n"
                f"Commune : {nom}\n"
                f"Département : {dept}"
            )
            if telephone:
                description += f"\nTél : {telephone}"
            if site:
                description += f"\nSite : {site}"

            offres.append({
                "nom": f"Mairie de {nom}",
                "email": email,
                "departement": dept,
                "secteur": "mairies",
                "type_organisation": "Mairie",
                "description": description,
                "date_scrape": datetime.now().isoformat(),
            })
            dept_count += 1

        avec_email = sum(1 for o in offres[-dept_count:] if o["email"])
        logger.info("scraper_mairies: dept %s — %d mairies (%d avec email)", dept, dept_count, avec_email)

    # Priorité aux mairies avec email
    offres.sort(key=lambda o: (0 if o["email"] else 1))

    total_email = sum(1 for o in offres if o["email"])
    logger.info("scraper_mairies: total %d mairies (%d avec email)", len(offres), total_email)
    return offres
