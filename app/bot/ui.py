"""
Utilitaires d'affichage partagés : emojis, formatage, claviers inline.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ─── Emojis statuts ───────────────────────────────────────────────────────────
STATUT_EMOJI = {
    "neuf":    "🆕",
    "prêt":    "✅",
    "envoyé":  "📤",
    "erreur":  "❌",
}

SECTEUR_EMOJI = {
    "mairies":   "🏛️",
    "education": "🎓",
}


def statut_label(statut: str) -> str:
    return f"{STATUT_EMOJI.get(statut, '•')} {statut}"


def secteur_label(secteur: str) -> str:
    return f"{SECTEUR_EMOJI.get(secteur, '•')} {secteur}"


# ─── Carte détail d'une cible ─────────────────────────────────────────────────

def format_cible_card(c: dict) -> str:
    emoji = SECTEUR_EMOJI.get(c.get("secteur", ""), "🏢")
    lines = [
        f"{emoji} *{c['nom']}*",
        "─────────────────────",
        f"📍 Dept : {c.get('departement', '—')}  |  {secteur_label(c.get('secteur', ''))}",
        f"📧 Email : {c.get('email') or '—'}",
        f"💼 Poste : {c.get('titre_poste') or '—'}",
        f"📊 Statut : {statut_label(c.get('statut', ''))}",
    ]
    if c.get("date_envoi"):
        lines.append(f"📅 Envoyé le : {c['date_envoi']}")
    return "\n".join(lines)


def keyboard_cible_actions(cible_id: str, has_lm: bool) -> InlineKeyboardMarkup:
    """Boutons d'action sur une fiche cible."""
    row1 = [InlineKeyboardButton("📝 Voir LM", callback_data=f"lm_view:{cible_id}")]
    if not has_lm:
        row1 = [InlineKeyboardButton("⚡ Générer LM", callback_data=f"regen:{cible_id}")]
    else:
        row1.append(InlineKeyboardButton("🔄 Régénérer", callback_data=f"regen:{cible_id}"))

    row2 = [InlineKeyboardButton("✉️ Envoyer", callback_data=f"send_confirm:{cible_id}")]
    row3 = [InlineKeyboardButton("◀️ Retour liste", callback_data="back_list")]

    return InlineKeyboardMarkup([row1, row2, row3])


def keyboard_send_confirm(cible_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmer", callback_data=f"send_go:{cible_id}"),
        InlineKeyboardButton("❌ Annuler", callback_data="send_cancel"),
    ]])


def keyboard_after_lm(cible_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✉️ Envoyer", callback_data=f"send_confirm:{cible_id}"),
        InlineKeyboardButton("🔄 Régénérer", callback_data=f"regen:{cible_id}"),
    ], [
        InlineKeyboardButton("◀️ Retour", callback_data="back_list"),
    ]])


# ─── Barre de progression ─────────────────────────────────────────────────────

def progress_bar(value: int, total: int, width: int = 10) -> str:
    if total == 0:
        return "▱" * width
    filled = round(value / total * width)
    return "▰" * filled + "▱" * (width - filled)
