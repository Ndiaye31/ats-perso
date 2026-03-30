"""
Construction et cycle de vie du bot Telegram.
Utilise python-telegram-bot v20+ en mode polling async.
start_bot / stop_bot sont appelés depuis app/main.py via on_event.
"""
import logging

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from app.config import settings

logger = logging.getLogger(__name__)

_application: Application | None = None


def _build_application() -> Application:
    from app.bot.commands.stats import cmd_stats, cmd_pipeline
    from app.bot.commands.targets import cmd_cibles, cmd_lm
    from app.bot.commands.generate import cmd_generer, cmd_generer_batch
    from app.bot.commands.send import cmd_envoyer_tous, confirm_envoyer_tous, CONFIRM_TOUS
    from app.bot.commands.scrape import cmd_scraper
    from app.bot.conversation.send_flow import build_send_flow_handler, cancel_handler
    from telegram.ext import ConversationHandler

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Commandes simples
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("pipeline", cmd_pipeline))
    app.add_handler(CommandHandler("cibles", cmd_cibles))
    app.add_handler(CommandHandler("lm", cmd_lm))
    app.add_handler(CommandHandler("generer", cmd_generer))
    app.add_handler(CommandHandler("generer_batch", cmd_generer_batch))
    app.add_handler(CommandHandler("scraper", cmd_scraper))
    app.add_handler(CommandHandler("annuler", cancel_handler))

    # Conversation /envoyer_un (multi-étapes)
    app.add_handler(build_send_flow_handler())

    # Conversation /envoyer_tous (confirmation simple)
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("envoyer_tous", cmd_envoyer_tous)],
            states={
                CONFIRM_TOUS: [
                    CallbackQueryHandler(confirm_envoyer_tous, pattern=r"^batch:")
                ],
            },
            fallbacks=[CommandHandler("annuler", cancel_handler)],
        )
    )

    return app


async def _cmd_start(update, context):
    """Message de bienvenue."""
    from app.bot.auth import require_authorized

    @require_authorized
    async def _inner(update, context):
        msg = (
            "Bot ATS — Candidatures spontanées\n\n"
            "/stats — comptages neuf/prêt/envoyé/erreur\n"
            "/pipeline — candidatures classiques\n"
            "/cibles [statut] — liste des cibles (défaut: prêt)\n"
            "/lm <id> — voir la lettre de motivation\n"
            "/generer <id> — générer la LM\n"
            "/generer_batch [n] — génération en masse\n"
            "/scraper [secteur] — scraper mairies/education\n"
            "/envoyer_un — envoyer une candidature (guidé)\n"
            "/envoyer_tous [n] — envoi en masse avec confirmation\n"
            "/annuler — annuler la conversation en cours"
        )
        await update.message.reply_text(msg)

    await _inner(update, context)


async def start_bot() -> None:
    global _application
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.error("Bot Telegram: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant — bot non démarré")
        return

    _application = _build_application()
    await _application.initialize()
    await _application.start()
    await _application.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot Telegram démarré (polling)")


async def stop_bot() -> None:
    global _application
    if _application is None:
        return
    await _application.updater.stop()
    await _application.stop()
    await _application.shutdown()
    logger.info("Bot Telegram arrêté")
