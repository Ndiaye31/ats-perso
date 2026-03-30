"""Commandes /generer et /generer_batch."""
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.auth import require_authorized
from app.bot import services


@require_authorized
async def cmd_generer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /generer <id_court>
    Génère la LM pour une cible et renvoie un aperçu.
    """
    if not context.args:
        await update.message.reply_text("Usage : /generer <id_court>")
        return

    prefix = context.args[0]
    cible = await services.get_cible_by_prefix(prefix)

    if cible is None:
        await update.message.reply_text("Cible introuvable.")
        return
    if cible.get("ambiguous"):
        await update.message.reply_text(
            f"Préfixe ambigu ({cible['count']} résultats). Précisez l'ID."
        )
        return

    msg = await update.message.reply_text(f"Génération en cours pour {cible['nom']}...")

    try:
        result = await services.generate_lm_for(cible["id"])
    except Exception as e:
        await msg.edit_text(f"Erreur lors de la génération : {e}")
        return

    if "error" in result:
        await msg.edit_text(f"Erreur : {result['error']}")
        return

    lm = result.get("lm_texte", "")
    header = f"LM générée pour {result['nom']}\n\n"
    full = header + lm
    if len(full) > 4000:
        full = full[:4000] + "\n[...tronqué]"
    await msg.edit_text(full)


@require_authorized
async def cmd_generer_batch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /generer_batch [limit]
    Génère les LM pour toutes les cibles 'neuf' avec email (défaut: 10).
    """
    limit = 10
    if context.args:
        try:
            limit = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Le limit doit être un entier.")
            return

    msg = await update.message.reply_text(f"Génération en masse (max {limit})...")

    try:
        result = await services.generate_batch(limit=limit)
    except Exception as e:
        await msg.edit_text(f"Erreur : {e}")
        return

    lines = [
        f"Génération terminée",
        f"  Générées : {result.get('generees', 0)}",
        f"  Erreurs  : {len(result.get('erreurs', []))}",
    ]
    if result.get("erreurs"):
        lines.append("\nErreurs :")
        for err in result["erreurs"][:5]:
            lines.append(f"  - {err}")
    await msg.edit_text("\n".join(lines))
