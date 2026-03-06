"""Génération de lettre de motivation via Claude API."""
from __future__ import annotations

from typing import Any

import anthropic

from app.config import settings


def generate_lm(
    title: str,
    company: str,
    description: str | None,
    profil: dict[str, Any],
) -> str:
    """Génère une lettre de motivation personnalisée via Claude."""
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY non configurée dans le fichier .env")

    # Extraction des compétences clés du profil
    competences = [c for cat in profil["competences"].values() for c in cat]
    experience_recente = profil["experiences"][0]

    prompt = f"""Tu es un rédacteur senior en communication professionnelle francophone.
Tu rédiges des lettres de motivation sobres, précises et crédibles, adaptées à tout secteur (public, privé, associatif).

MISSION
Rédiger une lettre de motivation personnalisée pour le poste fourni, en respectant strictement les règles ci-dessous.

DONNÉES ENTRÉE
- Poste: {title}
- Employeur: {company}
- Description du poste: {description or "Non disponible"}

- Candidat: {profil["nom"]}
- Résumé: {profil["resume"]}
- Compétences clés: {", ".join(competences[:12])}
- Expérience récente: {experience_recente["poste"]} chez {experience_recente["employeur"]} ({experience_recente["debut"]}–{experience_recente["fin"]})
- Formation: {profil["formation"][0]["diplome"]} — {profil["formation"][0]["etablissement"]}
- Certifications: {", ".join(profil.get("certifications", []))}

FORMAT IMPOSÉ
1) Première ligne exactement: Madame, Monsieur,
2) Exactement 3 paragraphes de corps (ni plus, ni moins).
3) Insérer une ligne vide entre chaque paragraphe.
4) Terminer exactement par les 2 lignes suivantes :
Je reste disponible pour toute information complémentaire.
Veuillez agréer, Madame, Monsieur, l'expression de mes sincères salutations.
5) Aucun en-tête administratif (pas d’adresse, pas de date, pas d’objet).
6) Longueur totale: 170 à 210 mots.

PLAN DES 3 PARAGRAPHES
- Paragraphe 1: motivation ciblée pour le poste et compréhension du besoin.
- Paragraphe 2: compétences pertinentes + 1 ou 2 faits concrets issus du parcours.
- Paragraphe 3: contribution attendue à court terme + conclusion professionnelle.

RÈGLES DE STYLE (OBLIGATOIRES)
- Ton formel, professionnel, direct.
- Français correct: ponctuation maîtrisée (virgules, points, deux-points), syntaxe claire.
- Phrases de longueur variée, sans lourdeur ni tournures creuses.
- Une idée principale par phrase.
- Aucun point d’exclamation.
- Aucun anglicisme inutile.
- Éviter les répétitions lexicales.

RÈGLES DE FOND (OBLIGATOIRES)
- Ne jamais inventer d’expérience, de compétence, d’outil, de résultat ou de contexte.
- Si l’information manque, rester prudent et général sans créer de faits.
- Relier explicitement les compétences du candidat aux besoins du poste.
- Ne pas mentionner de lacunes ou de points faibles.

INTERDICTIONS LEXICALES
Ne jamais utiliser:
"passionné", "dynamique", "rigoureux", "n'hésitez pas", "je reste à votre disposition", "Dans l'attente de votre réponse", "salutations distinguées", "n'est pas une faiblesse"

SORTIE ATTENDUE
Retourner uniquement la lettre finale, sans commentaire, sans titre, sans balises, sans explication."""

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
