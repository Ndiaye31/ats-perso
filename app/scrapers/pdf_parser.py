"""Extraction de texte et d'emails depuis des PDFs joints aux offres d'emploi."""
import logging
import re
from io import BytesIO

import pdfplumber
import requests

logger = logging.getLogger(__name__)

# Regex email — tolère les formats courants trouvés dans les PDFs RH
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def extract_from_pdf(url: str, headers: dict) -> dict:
    """Télécharge un PDF et retourne son texte brut + les emails trouvés.

    Returns:
        {"text": str | None, "emails": list[str]}
    """
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("PDF inaccessible %s : %s", url, e)
        return {"text": None, "emails": []}

    try:
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(pages_text).strip() or None
    except Exception as e:
        logger.warning("Erreur parsing PDF %s : %s", url, e)
        return {"text": None, "emails": []}

    emails = _EMAIL_RE.findall(text) if text else []
    # Dédoublonnage tout en conservant l'ordre
    seen: set[str] = set()
    unique_emails = [e for e in emails if not (e in seen or seen.add(e))]  # type: ignore[func-returns-value]

    logger.debug("PDF %s → %d page(s), %d email(s) trouvé(s).", url, len(pages_text), len(unique_emails))
    return {"text": text, "emails": unique_emails}
