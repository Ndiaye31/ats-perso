"""Sécurité : seul le TELEGRAM_CHAT_ID autorisé peut interagir avec le bot."""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings

logger = logging.getLogger(__name__)


def require_authorized(handler_func):
    """Décorateur : droppe silencieusement tout message d'un chat non autorisé."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id) if update.effective_chat else ""
        if chat_id != str(settings.telegram_chat_id):
            logger.warning("Bot Telegram: accès non autorisé chat_id=%s", chat_id)
            return
        return await handler_func(update, context)
    return wrapper
