"""Commande /envoyer_tous avec confirmation inline."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.auth import require_authorized
from app.bot import services

CONFIRM_TOUS = 10


@require_authorized
async def cmd_envoyer_tous(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Usage: /envoyer_tous [limit]
    Envoie tous les emails des cibles 'prêt' après confirmation.
    """
    limit = 20
    if context.args:
        try:
            limit = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Le limit doit être un entier.")
            return ConversationHandler.END

    # Compte les cibles prêtes
    cibles = await services.list_cibles(statut="prêt", limit=limit)
    if not cibles:
        await update.message.reply_text("Aucune cible prête à envoyer.")
        return ConversationHandler.END

    context.user_data["send_batch_limit"] = limit

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("OUI ✓", callback_data="batch:yes"),
            InlineKeyboardButton("NON ✗", callback_data="batch:no"),
        ]
    ])
    await update.message.reply_text(
        f"Envoyer {len(cibles)} candidature(s) (statut=prêt) ?",
        reply_markup=keyboard,
    )
    return CONFIRM_TOUS


async def confirm_envoyer_tous(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "batch:no":
        await query.edit_message_text("Annulé.")
        return ConversationHandler.END

    limit = context.user_data.get("send_batch_limit", 20)
    await query.edit_message_text("Envoi en cours...")

    try:
        result = await services.send_batch(limit=limit)
    except Exception as e:
        await query.edit_message_text(f"Erreur lors de l'envoi : {e}")
        return ConversationHandler.END

    lines = [
        "Envoi terminé",
        f"  Envoyés : {result.get('envoyes', 0)}",
        f"  Erreurs : {len(result.get('erreurs', []))}",
    ]
    if result.get("erreurs"):
        lines.append("\nErreurs :")
        for err in result["erreurs"][:5]:
            lines.append(f"  - {err}")
    await query.edit_message_text("\n".join(lines))
    return ConversationHandler.END
