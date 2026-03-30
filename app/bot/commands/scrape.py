"""Commande /scraper."""
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.auth import require_authorized
from app.bot import services


@require_authorized
async def cmd_scraper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /scraper [secteur]
    Exemples: /scraper | /scraper mairies | /scraper education
    """
    secteur = context.args[0] if context.args else None

    if secteur and secteur not in ("mairies", "education"):
        await update.message.reply_text(
            "⚠️ Secteur invalide.\nUsage : /scraper | /scraper mairies | /scraper education"
        )
        return

    label = f"🏛️ mairies + 🎓 éducation" if not secteur else (
        "🏛️ mairies" if secteur == "mairies" else "🎓 éducation"
    )
    msg = await update.message.reply_text(f"🔍 Scraping en cours ({label})…")

    try:
        result = await services.run_scrape(secteur=secteur)
    except Exception as e:
        await msg.edit_text(f"❌ Erreur lors du scraping : {e}")
        return

    inseres = result.get("inseres", 0)
    lines = [
        f"✅ *Scraping terminé* — {label}",
        f"  🆕 Nouvelles cibles : {inseres}",
        f"  ♻️ Doublons ignorés  : {result.get('ignores', 0)}",
        f"  📦 Total collecté   : {result.get('total', 0)}",
    ]
    if inseres > 0:
        lines.append(f"\n💡 Lance /generer\\_batch pour générer les LM")

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")
