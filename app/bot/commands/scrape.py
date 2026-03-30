"""Commande /scraper."""
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.auth import require_authorized
from app.bot import services


@require_authorized
async def cmd_scraper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /scraper [secteur]
    Déclenche le scraping (mairies, education, ou les deux si omis).
    """
    secteur = context.args[0] if context.args else None

    if secteur and secteur not in ("mairies", "education"):
        await update.message.reply_text("Secteur invalide. Utiliser : mairies, education, ou rien pour les deux.")
        return

    label = secteur or "mairies + education"
    msg = await update.message.reply_text(f"Scraping en cours ({label})...")

    try:
        result = await services.run_scrape(secteur=secteur)
    except Exception as e:
        await msg.edit_text(f"Erreur lors du scraping : {e}")
        return

    lines = [
        f"Scraping terminé ({label})",
        f"  Insérées : {result.get('inseres', 0)}",
        f"  Doublons : {result.get('ignores', 0)}",
        f"  Total    : {result.get('total', 0)}",
    ]
    await msg.edit_text("\n".join(lines))
