"""Commandes /cibles et /lm."""
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.auth import require_authorized
from app.bot import services


@require_authorized
async def cmd_cibles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /cibles [statut]
    Liste jusqu'à 15 cibles filtrées par statut (défaut: prêt).
    """
    statut = context.args[0] if context.args else "prêt"
    try:
        cibles = await services.list_cibles(statut=statut, limit=15)
    except Exception as e:
        await update.message.reply_text(f"Erreur : {e}")
        return

    if not cibles:
        await update.message.reply_text(f"Aucune cible avec statut '{statut}'.")
        return

    lines = [f"Cibles [{statut}] ({len(cibles)})"]
    for i, c in enumerate(cibles, 1):
        short_id = c["id"][:8]
        email_icon = " 📧" if c.get("email") else ""
        lines.append(f"{i}. [{short_id}] {c['nom']}{email_icon}")

    lines.append("\nUtiliser /lm <id> pour voir la lettre de motivation.")
    await update.message.reply_text("\n".join(lines))


@require_authorized
async def cmd_lm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /lm <id_court>
    Affiche la lettre de motivation d'une cible (préfixe UUID sur 8+ chars).
    """
    if not context.args:
        await update.message.reply_text("Usage : /lm <id_court>")
        return

    prefix = context.args[0]
    try:
        cible = await services.get_cible_by_prefix(prefix)
    except Exception as e:
        await update.message.reply_text(f"Erreur : {e}")
        return

    if cible is None:
        await update.message.reply_text("Cible introuvable.")
        return
    if cible.get("ambiguous"):
        await update.message.reply_text(
            f"Préfixe ambigu ({cible['count']} résultats). Précisez l'ID."
        )
        return

    lm = cible.get("lm_texte")
    if not lm:
        await update.message.reply_text(
            f"{cible['nom']} — pas encore de LM générée.\n"
            f"Utiliser : /generer {prefix}"
        )
        return

    header = f"{cible['nom']} [{cible['statut']}]\n\n"
    full = header + lm
    # Limite Telegram : 4096 chars
    if len(full) > 4000:
        full = full[:4000] + "\n[...tronqué]"
    await update.message.reply_text(full)
