"""Scoring d'une offre vs le profil utilisateur (0–100)."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.offer import Offer

SKILL_KEYWORDS: list[str] = [
    "power bi", "sql", "postgresql", "python", "etl", "sharepoint",
    "power automate", "power apps", "excel", "vba", "pandas", "numpy",
    "reporting", "tableau de bord", "kpi", "data quality",
    "git", "github", "gitlab",
]

TITLE_TRIGGERS: list[str] = [
    "data", "analyst", "analyste", "reporting", "décisionnel",
    "sharepoint", "intelligence", "pilotage", "données",
    "informatique", "technicien", "développeur", "developpeur",
    "logiciel", "applicatif", "numérique", "digital",
]

# Mots courants à ignorer lors du matching de postes
_STOP = {
    "de", "du", "des", "le", "la", "les", "un", "une", "et", "en",
    "au", "aux", "par", "sur", "dans", "avec", "pour", "d", "l",
}


def _sig_words(text: str) -> list[str]:
    """Mots significatifs : >= 4 caractères, hors mots courants."""
    return [
        w for w in re.findall(r"[a-zéèêàùîôâûç]+", text.lower())
        if len(w) >= 4 and w not in _STOP
    ]


def _word_in_text(word: str, text: str) -> bool:
    """Vérifie si le mot apparaît en tant que mot entier dans le texte."""
    return bool(re.search(r"\b" + re.escape(word) + r"\b", text))


MIN_SCORE = 20  # Seuil minimum — offres en dessous ignorées


def _term_in_text(term: str, text: str) -> bool:
    """Match robuste d'un terme interdit (mot ou expression) dans un texte."""
    t = (term or "").strip().lower()
    if not t:
        return False
    if " " in t:
        parts = [re.escape(p) for p in t.split() if p]
        if not parts:
            return False
        pattern = r"\b" + r"\s+".join(parts) + r"\b"
        return bool(re.search(pattern, text))
    return _word_in_text(t, text)


def _coverage_ratio(words: list[str], text: str) -> float:
    """Part des mots significatifs retrouvés dans le texte."""
    if not words:
        return 0.0
    matched = sum(1 for w in words if _word_in_text(w, text))
    return matched / len(words)


def score_offer(offer: "Offer", profil: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Retourne (score 0-100, details dict).

    Répartition :
      - Titre      : 50 pts  (match poste cible exact > fallback desc > trigger générique)
      - Compétences: 40 pts  (8 pts/skill, plafonné à 40)
      - Contrat    : 10 pts
    Localisation retirée : profil mobile partout en France.
    """
    prefs = profil["preferences"]
    title = (offer.title or "").lower()
    desc  = (offer.description or "").lower()
    text  = f"{title} {desc}"
    ratio_min = float(prefs.get("title_match_ratio_min", 0.6))

    # Rejet strict si le titre contient un métier explicitement hors cible
    forbidden_terms = [str(t).lower().strip() for t in prefs.get("mots_interdits_titre", []) if str(t).strip()]
    blacklist_hits = [t for t in forbidden_terms if _term_in_text(t, title)]
    if blacklist_hits:
        details: dict[str, Any] = {
            "title_score": 0,
            "skills_score": 0,
            "contract_score": 0,
            "matched_postes": [],
            "matched_skills": [],
            "matched_contract": None,
            "title_match_ratio": 0.0,
            "rejected_by_blacklist": True,
            "blacklist_hits": blacklist_hits,
            "total": 0,
        }
        return 0, details

    # Titre (50 pts)
    postes = [p.lower() for p in prefs["postes_cibles"]]
    matched_postes: list[str] = []
    best_title_ratio = 0.0
    best_desc_ratio = 0.0

    for poste in postes:
        words = _sig_words(poste)
        ratio_title = _coverage_ratio(words, title)
        best_title_ratio = max(best_title_ratio, ratio_title)
        if ratio_title >= ratio_min:
            matched_postes.append(poste)

    if matched_postes:
        title_score = 50
    elif desc:
        matched_postes_desc: list[str] = []
        for poste in postes:
            words = _sig_words(poste)
            ratio_desc = _coverage_ratio(words, desc)
            best_desc_ratio = max(best_desc_ratio, ratio_desc)
            if ratio_desc >= ratio_min:
                matched_postes_desc.append(poste)
        if matched_postes_desc:
            matched_postes = matched_postes_desc
            title_score = 30
        elif any(t in title for t in TITLE_TRIGGERS):
            title_score = 15
        else:
            title_score = 0
    elif any(t in title for t in TITLE_TRIGGERS):
        title_score = 15
    else:
        title_score = 0

    # Compétences (40 pts — 8 pts par skill)
    matched_skills = [s for s in SKILL_KEYWORDS if s in text]
    skills_score = min(40, len(matched_skills) * 8)

    # Contrat (10 pts)
    types = [t.lower() for t in prefs["types_contrat"]]
    matched_contract = next((t for t in types if t in text), None)
    contract_score = 10 if matched_contract else 0

    total = title_score + skills_score + contract_score
    details: dict[str, Any] = {
        "title_score": title_score,
        "skills_score": skills_score,
        "contract_score": contract_score,
        "matched_postes": matched_postes[:3],
        "matched_skills": matched_skills,
        "matched_contract": matched_contract,
        "title_match_ratio": round(max(best_title_ratio, best_desc_ratio), 3),
        "rejected_by_blacklist": False,
        "blacklist_hits": [],
        "total": total,
    }
    return total, details
