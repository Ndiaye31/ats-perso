"""
Génération de lettres de motivation pour candidatures spontanées (mairies / éducation).
Utilise le même profil.yml que les candidatures plateforme, mais adapte la mise en valeur
selon le secteur : compétences admin et organisationnelles en avant, pas de Data Analyst / BI.
"""
from __future__ import annotations

import re
from typing import Any

import anthropic

from app.config import settings
from app.profil import load_profil

# Contexte sectoriel : (type d'organisation, milieu, consigne spécifique)
_CONTEXTES: dict[str, tuple[str, str, str]] = {
    "mairies": (
        "une mairie ou collectivité territoriale",
        "service public local",
        (
            "Valoriser le sens du service public, le contact avec les administrés et la polyvalence. "
            "Mettre en avant : organisation documentaire, coordination multi-services, outils Microsoft 365, "
            "suivi d'activité et structuration des processus."
        ),
    ),
    "education": (
        "un établissement scolaire (lycée, collège, CIO ou GRETA)",
        "service public éducatif",
        (
            "Souligner l'adaptabilité au milieu éducatif et le sens du service. "
            "Mettre en avant : gestion administrative, suivi de dossiers, outils numériques (M365), "
            "organisation et rigueur opérationnelle."
        ),
    ),
}

_CONTEXTE_DEFAULT = _CONTEXTES["mairies"]


def _build_prompt(employeur: str, titre_poste: str, secteur: str, profil: dict[str, Any]) -> str:
    org_type, milieu, consigne = _CONTEXTES.get(secteur, _CONTEXTE_DEFAULT)

    # Expérience récente
    exp = profil["experiences"][0]

    # Compétences admin pertinentes tirées du profil (M365, GED, coordination, reporting)
    # On exclut les items purement BI/data pour ce contexte
    _MOTS_EXCLUS = {"power bi", "sql", "python", "pandas", "numpy", "etl", "dax", "vba", "jira", "git"}
    toutes_competences = [
        c for cat in profil["competences"].values() for c in cat
    ]
    competences_admin = [
        c for c in toutes_competences
        if not any(exclu in c.lower() for exclu in _MOTS_EXCLUS)
    ]

    # Responsabilités orientées admin (exclure celles trop techniques)
    _MOTS_EXCLUS_RESP = {"sql", "python", "etl", "power bi", "dax", "modélisation", "numpy", "pandas"}
    responsabilites_admin = [
        r for r in exp["responsabilites"]
        if not any(m in r.lower() for m in _MOTS_EXCLUS_RESP)
    ]

    competences_str = "\n".join(f"- {c}" for c in competences_admin[:8])
    responsabilites_str = "\n".join(f"- {r}" for r in responsabilites_admin[:6])

    mots_interdits = (
        '"passionné", "dynamique", "rigoureux", "n\'hésitez pas", '
        '"je reste à votre disposition", "dans l\'attente de votre réponse", '
        '"salutations distinguées", "cordialement"'
    )

    return f"""Tu es un rédacteur senior en communication professionnelle francophone.
Tu rédiges des lettres de motivation sobres, précises et crédibles pour des candidatures administratives.

CONTEXTE IMPORTANT
Il s'agit d'une CANDIDATURE SPONTANÉE : aucun poste n'est ouvert, aucune offre n'a été publiée.
Le candidat se présente de sa propre initiative pour proposer ses services à cette organisation.

DONNÉES DE LA CANDIDATURE
- Type de poste visé : {titre_poste}
- Organisation ciblée : {employeur} ({org_type})
- Candidat : {profil["nom"]}, basé à {profil["localisation"]}

EXPÉRIENCE RÉCENTE ({exp["poste"]} chez {exp["employeur"]}, {exp["debut"]}–{exp["fin"]})
{responsabilites_str}

COMPÉTENCES CLÉS POUR CE PROFIL
{competences_str}

FORMAT IMPOSÉ
1) Première ligne exactement : Madame, Monsieur,
2) Exactement 3 paragraphes de corps, séparés par une ligne vide.
3) Terminer exactement par ces 2 lignes :
Je reste disponible pour toute information complémentaire.
Veuillez agréer, Madame, Monsieur, l'expression de mes sincères salutations.
4) Aucun en-tête, aucune date, aucun objet, aucune adresse.
5) Longueur totale : 170 à 210 mots.
6) Aucun formatage Markdown (pas de **, *, #, tirets de liste dans le corps).

PLAN DES 3 PARAGRAPHES
- §1 : Le candidat exprime sa démarche proactive : pourquoi il souhaite rejoindre ce type de structure ({milieu}) et le lien avec son parcours. Ne pas sous-entendre qu'un poste est ouvert.
- §2 : 2 ou 3 compétences concrètes tirées de l'expérience réelle, montrant ce qu'il peut apporter au {milieu}.
- §3 : Disponibilité, contribution envisagée et ouverture à un échange.

CONSIGNE SECTORIELLE
{consigne}

RÈGLES DE STYLE
- Ton formel, direct, sans emphase excessive.
- Phrases courtes à moyennes, une idée par phrase.
- Pas de point d'exclamation.
- Pas d'anglicisme inutile.
- Pas de répétition lexicale entre les paragraphes.

INTERDICTIONS ABSOLUES
- Ne jamais écrire que l'organisation "recherche" quelqu'un ou qu'un poste est "proposé", "disponible" ou "ouvert".
- Ne jamais utiliser : "l'offre", "le poste proposé", "votre annonce", "votre offre", "en réponse à".
- Ne jamais mentionner : Power BI, SQL, Python, Data Analyst, data, DAX, ETL, VBA — hors sujet pour ce profil.
- Ne jamais utiliser : {mots_interdits}
- Ne jamais inventer d'expérience, de résultat chiffré ou de contexte non fourni.

SORTIE ATTENDUE
Retourner uniquement la lettre finale, sans commentaire, sans titre, sans balise."""


def _clean(text: str) -> str:
    """Supprime les artefacts Markdown et les signatures dupliquées."""
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"\n+Amadou\s+Mactar\s+Ndiaye\s*$", "", text, flags=re.IGNORECASE)
    return text.strip()


def generate_lm_spontane(
    employeur: str,
    secteur: str,
    titre_poste: str | None = None,
) -> str:
    """
    Génère une lettre de motivation spontanée adaptée au secteur.

    Args:
        employeur: Nom de l'organisation (ex. "Mairie de Chessy").
        secteur: "mairies" ou "education".
        titre_poste: Intitulé du poste (optionnel, sinon déduit du secteur).
    """
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY non configurée dans le fichier .env")

    profil = load_profil()

    if not titre_poste:
        titre_poste = (
            "Assistant(e) Administratif(ve) — Candidature Spontanée"
            if secteur == "mairies"
            else "Gestionnaire administratif / Assistant d'établissement — Candidature Spontanée"
        )

    prompt = _build_prompt(employeur, titre_poste, secteur, profil)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return _clean(message.content[0].text)
