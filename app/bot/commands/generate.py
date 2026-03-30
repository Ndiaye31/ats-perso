"""Commandes /generer et /generer_batch."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.bot.auth import require_authorized
from app.bot import services
from app.bot.ui import keyboard_after_lm


@require_authorized
async def cmd_generer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /generer <id_court>
    Génère la LM pour une cible et renvoie un aperçu avec bouton d'envoi.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage : /generer <id_court>\n\nOu utilise /cibles pour naviguer sans ID."
        )
        return

    prefix = context.args[0]
    cible = await services.get_cible_by_prefix(prefix)

    if cible is None:
        await update.message.reply_text("❌ Cible introuvable.")
        return
    if cible.get("ambiguous"):
        await update.message.reply_text(f"⚠️ Préfixe ambigu ({cible['count']} résultats). Précisez l'ID.")
        return

    msg = await update.message.reply_text(f"⚡ Génération en cours pour *{cible['nom']}*…", parse_mode="Markdown")

    result = await services.generate_lm_for(cible["id"])

    if "error" in result:
        await msg.edit_text(f"❌ Erreur : {result['error']}")
        return

    lm = result.get("lm_texte", "")
    cible_id = result.get("id", cible["id"])
    header = f"✅ *LM générée — {result['nom']}*\n\n"
    full = header + lm
    if len(full) > 4000:
        full = full[:4000] + "\n\\[…tronqué]"

    await msg.edit_text(full, reply_markup=keyboard_after_lm(cible_id), parse_mode="Markdown")


@require_authorized
async def cmd_generer_batch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /generer_batch [limit] [dept]
    Exemples: /generer_batch 20 | /generer_batch 10 77
    """
    args = context.args or []
    limit = 10
    dept = None

    for a in args:
        if a.isdigit() and len(a) <= 3:
            if len(a) == 2:
                dept = a
            else:
                limit = int(a)
        elif a.isdigit():
            limit = int(a)

    label = f"max {limit}"
    if dept:
        label += f" · dept {dept}"

    msg = await update.message.reply_text(f"⚡ Génération en masse ({label})…")

    result = await services.generate_batch(limit=limit, departement=dept)

    generees = result.get("generees", 0)
    nb_erreurs = len(result.get("erreurs", []))

    lines = [
        f"✅ *Génération terminée*",
        f"  Générées : {generees}",
        f"  Erreurs  : {nb_erreurs}",
    ]
    if result.get("erreurs"):
        lines.append("\n⚠️ Erreurs :")
        for err in result["erreurs"][:5]:
            lines.append(f"  • {err}")

    if generees > 0:
        lines.append(f"\n💡 {generees} LM prêtes — /envoyer\\_tous pour envoyer")

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")
