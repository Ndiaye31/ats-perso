"""Commandes /stats et /pipeline."""
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.auth import require_authorized
from app.bot import services


@require_authorized
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Affiche les comptages neuf/prêt/envoyé/erreur pour les candidatures spontanées."""
    await update.message.reply_text("Récupération des stats...")
    try:
        stats = await services.get_stats()
    except Exception as e:
        await update.message.reply_text(f"Erreur : {e}")
        return

    lines = [
        "Candidatures spontanées",
        f"  neuf    : {stats.get('neuf', 0)}",
        f"  prêt    : {stats.get('prêt', 0)}",
        f"  envoyé  : {stats.get('envoyé', 0)}",
        f"  erreur  : {stats.get('erreur', 0)}",
        f"  TOTAL   : {stats.get('total', 0)}",
    ]
    await update.message.reply_text("\n".join(lines))


@require_authorized
async def cmd_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Aperçu des candidatures classiques par statut."""
    try:
        stats = await services.get_pipeline()
    except Exception as e:
        await update.message.reply_text(f"Erreur : {e}")
        return

    total = stats.pop("total", 0)
    lines = ["Candidatures classiques"]
    for statut, count in sorted(stats.items()):
        lines.append(f"  {statut:<12}: {count}")
    lines.append(f"  TOTAL       : {total}")
    await update.message.reply_text("\n".join(lines))
