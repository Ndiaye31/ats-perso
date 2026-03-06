import hashlib


def compute_content_hash(title: str, company: str, location: str | None = None) -> str:
    """SHA-256 de (titre + employeur + ville) normalisés — utilisé pour la déduplication.

    Utilise la ville plutôt que l'URL : une même offre republiée sur plusieurs sites
    (emploi-territorial, place-emploi-public, site de la collectivité) sera détectée
    comme doublon même si ses URLs diffèrent.
    """
    raw = (
        f"{title.lower().strip()}"
        f"|{company.lower().strip()}"
        f"|{(location or '').lower().strip()}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()
