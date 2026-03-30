"""
Construction et cycle de vie du bot Telegram.
Utilise python-telegram-bot v20+ en mode polling async.
start_bot / stop_bot sont appelés depuis app/main.py via on_event.
"""
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
)

from app.config import settings

logger = logging.getLogger(__name__)

_application: Application | None = None


def _build_application() -> Application:
    from app.bot.commands.stats import cmd_stats, cmd_pipeline
    from app.bot.commands.targets import cmd_cibles, cmd_lm
    from app.bot.commands.generate import cmd_generer, cmd_generer_batch
    from app.bot.commands.send import cmd_envoyer_tous, confirm_envoyer_tous, CONFIRM_TOUS
    from app.bot.commands.scrape import cmd_scraper
    from app.bot.commands.actions import (
        handle_detail, handle_lm_view, handle_regen,
        handle_send_confirm, handle_send_go, handle_send_cancel, handle_back_list,
    )
    from app.bot.conversation.send_flow import build_send_flow_handler, cancel_handler

    app = Application.builder().token(settings.telegram_bot_token).build()

    # ─── Commandes ────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("aide", _cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("pipeline", cmd_pipeline))
    app.add_handler(CommandHandler("cibles", cmd_cibles))
    app.add_handler(CommandHandler("lm", cmd_lm))
    app.add_handler(CommandHandler("generer", cmd_generer))
    app.add_handler(CommandHandler("generer_batch", cmd_generer_batch))
    app.add_handler(CommandHandler("scraper", cmd_scraper))
    app.add_handler(CommandHandler("annuler", cancel_handler))

    # ─── Conversations ────────────────────────────────────────────────────────
    app.add_handler(build_send_flow_handler())

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

    # ─── Callbacks inline (navigation sans saisie d'ID) ───────────────────────
    app.add_handler(CallbackQueryHandler(handle_detail,       pattern=r"^detail:"))
    app.add_handler(CallbackQueryHandler(handle_lm_view,      pattern=r"^lm_view:"))
    app.add_handler(CallbackQueryHandler(handle_regen,        pattern=r"^regen:"))
    app.add_handler(CallbackQueryHandler(handle_send_confirm, pattern=r"^send_confirm:"))
    app.add_handler(CallbackQueryHandler(handle_send_go,      pattern=r"^send_go:"))
    app.add_handler(CallbackQueryHandler(handle_send_cancel,  pattern=r"^send_cancel$"))
    app.add_handler(CallbackQueryHandler(handle_back_list,    pattern=r"^back_list$"))

    return app


async def _cmd_start(update: Update, context) -> None:
    from app.bot.auth import require_authorized

    @require_authorized
    async def _inner(update, context):
        msg = (
            "🤖 *Bot ATS — Candidatures spontanées*\n"
            "─────────────────────\n"
            "\n"
            "📊 *Tableau de bord*\n"
            "  /stats — neuf · prêt · envoyé · erreur\n"
            "  /pipeline — candidatures classiques\n"
            "\n"
            "📋 *Explorer les cibles*\n"
            "  /cibles — liste prêtes (tapable, sans ID)\n"
            "  /cibles neuf 77 — filtre dept + statut\n"
            "  /cibles prêt mairies — filtre secteur\n"
            "\n"
            "⚡ *Générer des LM*\n"
            "  /generer\\_batch 20 — en masse\n"
            "  /generer\\_batch 10 77 — dept 77\n"
            "\n"
            "🔍 *Scraper*\n"
            "  /scraper — mairies + éducation\n"
            "  /scraper mairies | /scraper education\n"
            "\n"
            "✉️ *Envoyer*\n"
            "  /envoyer\\_un — guidé avec confirmation\n"
            "  /envoyer\\_tous 20 — en masse\n"
            "\n"
            "💡 *Astuce* : dans /cibles, clique directement sur "
            "une cible pour voir sa fiche et agir dessus — sans taper d'ID !"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

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
