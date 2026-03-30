"""
ConversationHandler pour /envoyer_un.
Flow : lister les cibles prêtes → sélectionner → confirmer → envoyer.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
)

from app.bot.auth import require_authorized
from app.bot import services

SELECT = 0
CONFIRM = 1


@require_authorized
async def envoyer_un_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Point d'entrée : liste les cibles 'prêt' avec boutons inline."""
    cibles = await services.list_cibles(statut="prêt", limit=10)

    if not cibles:
        await update.message.reply_text("Aucune cible prête à envoyer.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(c["nom"][:40], callback_data=f"select:{c['id']}")]
        for c in cibles
    ]
    keyboard.append([InlineKeyboardButton("Annuler", callback_data="select:cancel")])

    await update.message.reply_text(
        f"Choisir une cible à envoyer ({len(cibles)} prêtes) :",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SELECT


async def envoyer_un_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """L'utilisateur a sélectionné une cible — demande confirmation."""
    query = update.callback_query
    await query.answer()

    data = query.data.replace("select:", "")
    if data == "cancel":
        await query.edit_message_text("Annulé.")
        return ConversationHandler.END

    cible_id = data
    context.user_data["selected_cible_id"] = cible_id

    # Récupère les détails de la cible
    cible = await services.get_cible_by_prefix(cible_id[:8])
    if not cible or cible.get("ambiguous"):
        await query.edit_message_text("Cible introuvable. Réessayez avec /envoyer_un.")
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("OUI ✓", callback_data="confirm:yes"),
            InlineKeyboardButton("NON ✗", callback_data="confirm:no"),
        ]
    ])
    email = cible.get("email", "?")
    await query.edit_message_text(
        f"Envoyer à {cible['nom']} <{email}> ?",
        reply_markup=keyboard,
    )
    return CONFIRM


async def envoyer_un_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """L'utilisateur confirme ou annule l'envoi."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm:no":
        await query.edit_message_text("Annulé.")
        return ConversationHandler.END

    cible_id = context.user_data.get("selected_cible_id")
    if not cible_id:
        await query.edit_message_text("Erreur : cible perdue. Réessayez avec /envoyer_un.")
        return ConversationHandler.END

    await query.edit_message_text("Envoi en cours...")

    try:
        result = await services.send_one(cible_id)
    except Exception as e:
        await query.edit_message_text(f"Erreur lors de l'envoi : {e}")
        return ConversationHandler.END

    if "error" in result:
        await query.edit_message_text(f"Erreur : {result['error']}")
    else:
        await query.edit_message_text(
            f"Email envoyé à {result['nom']} ({result['email']})"
        )
    return ConversationHandler.END


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Conversation annulée.")
    return ConversationHandler.END


def build_send_flow_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("envoyer_un", envoyer_un_start)],
        states={
            SELECT: [CallbackQueryHandler(envoyer_un_selected, pattern=r"^select:")],
            CONFIRM: [CallbackQueryHandler(envoyer_un_confirmed, pattern=r"^confirm:")],
        },
        fallbacks=[CommandHandler("annuler", cancel_handler)],
    )
