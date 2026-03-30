"""
Commandes /cibles et /lm.
Navigation entièrement via boutons inline — plus besoin de taper les IDs.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.bot.auth import require_authorized
from app.bot import services
from app.bot.ui import (
    SECTEUR_EMOJI, STATUT_EMOJI,
    format_cible_card, keyboard_cible_actions, keyboard_after_lm,
)

DEPTS_IDF = ["75", "77", "78", "91", "92", "93", "94", "95"]


def _parse_args(args: list[str]) -> tuple[str, str | None, str | None]:
    """Parse: /cibles [statut] [dept] — dans n'importe quel ordre."""
    statut = "prêt"
    dept = None
    secteur = None
    for a in args:
        if a in ("neuf", "prêt", "pret", "envoyé", "envoye", "erreur"):
            statut = a.replace("pret", "prêt").replace("envoye", "envoyé")
        elif a.isdigit() and len(a) == 2:
            dept = a
        elif a in ("mairies", "education"):
            secteur = a
    return statut, dept, secteur


@require_authorized
async def cmd_cibles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /cibles [statut] [dept] [secteur]
    Exemples: /cibles prêt 77 | /cibles neuf mairies | /cibles envoyé 93
    """
    statut, dept, secteur = _parse_args(context.args or [])

    try:
        cibles = await services.list_cibles(
            statut=statut, limit=15, departement=dept, secteur=secteur
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur : {e}")
        return

    # Sauvegarde le contexte pour le bouton "retour"
    context.user_data["last_list_args"] = context.args or []

    if not cibles:
        filtre = f"statut={statut}"
        if dept: filtre += f" | dept={dept}"
        if secteur: filtre += f" | {secteur}"
        await update.message.reply_text(f"Aucune cible trouvée ({filtre}).")
        return

    # Header
    filtre_label = f"{STATUT_EMOJI.get(statut, '')} {statut}"
    if dept: filtre_label += f" · Dept {dept}"
    if secteur: filtre_label += f" · {SECTEUR_EMOJI.get(secteur, '')} {secteur}"

    header = f"📋 *Cibles — {filtre_label}* ({len(cibles)} résultats)\n─────────────────────"

    # Boutons : 1 ligne par cible, nom tronqué + emoji email
    keyboard = []
    for c in cibles:
        email_icon = " 📧" if c.get("email") else " ✗"
        dept_label = f" [{c.get('departement', '?')}]" if not dept else ""
        label = f"{SECTEUR_EMOJI.get(c['secteur'], '•')} {c['nom'][:30]}{dept_label}{email_icon}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"detail:{c['id']}")])

    await update.message.reply_text(
        header,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


@require_authorized
async def cmd_lm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /lm <id_court>  (encore supporté mais le menu inline est préférable)
    """
    if not context.args:
        await update.message.reply_text(
            "Usage : /lm <id_court>\n\nOu utilise /cibles pour naviguer sans ID."
        )
        return

    prefix = context.args[0]
    cible = await services.get_cible_by_prefix(prefix)

    if cible is None:
        await update.message.reply_text("❌ Cible introuvable.")
        return
    if cible.get("ambiguous"):
        await update.message.reply_text(
            f"⚠️ Préfixe ambigu ({cible['count']} résultats). Précisez l'ID."
        )
        return

    await _show_lm(update.message.reply_text, cible)


async def _show_lm(reply_fn, cible: dict) -> None:
    """Affiche la LM avec boutons d'action."""
    lm = cible.get("lm_texte")
    cible_id = cible["id"]

    if not lm:
        await reply_fn(
            f"⚠️ *{cible['nom']}* — aucune LM générée.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚡ Générer la LM", callback_data=f"regen:{cible_id}"),
            ]]),
            parse_mode="Markdown",
        )
        return

    header = f"📝 *{cible['nom']}* — {STATUT_EMOJI.get(cible['statut'], '')} {cible['statut']}\n\n"
    full = header + lm
    if len(full) > 4000:
        full = full[:4000] + "\n\\[…tronqué]"

    await reply_fn(
        full,
        reply_markup=keyboard_after_lm(cible_id),
        parse_mode="Markdown",
    )
