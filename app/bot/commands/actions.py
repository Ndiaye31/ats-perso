"""
Gestionnaire de toutes les callbacks inline du bot.
Centralise : affichage détail, voir LM, régénérer, confirmer/envoyer.
"""
from telegram import Update
from telegram.ext import ContextTypes

from app.bot import services
from app.bot.ui import (
    format_cible_card,
    keyboard_cible_actions,
    keyboard_after_lm,
    keyboard_send_confirm,
)


async def handle_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Affiche la fiche détail d'une cible (callback: detail:<uuid>)."""
    query = update.callback_query
    await query.answer()

    cible_id = query.data.replace("detail:", "")
    cible = await services.get_cible_by_id(cible_id)

    if not cible:
        await query.edit_message_text("❌ Cible introuvable.")
        return

    text = format_cible_card(cible)
    keyboard = keyboard_cible_actions(cible_id, has_lm=bool(cible.get("lm_texte")))
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def handle_lm_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Affiche la LM d'une cible (callback: lm_view:<uuid>)."""
    query = update.callback_query
    await query.answer()

    cible_id = query.data.replace("lm_view:", "")
    cible = await services.get_cible_by_id(cible_id)

    if not cible:
        await query.edit_message_text("❌ Cible introuvable.")
        return

    lm = cible.get("lm_texte")
    if not lm:
        await query.edit_message_text(
            f"⚠️ *{cible['nom']}* — aucune LM générée.",
            reply_markup=keyboard_cible_actions(cible_id, has_lm=False),
            parse_mode="Markdown",
        )
        return

    from app.bot.ui import STATUT_EMOJI
    header = f"📝 *{cible['nom']}* — {STATUT_EMOJI.get(cible['statut'], '')} {cible['statut']}\n\n"
    full = header + lm
    if len(full) > 4000:
        full = full[:4000] + "\n\\[…tronqué]"

    await query.edit_message_text(
        full,
        reply_markup=keyboard_after_lm(cible_id),
        parse_mode="Markdown",
    )


async def handle_regen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Régénère la LM (callback: regen:<uuid>)."""
    query = update.callback_query
    await query.answer("Génération en cours…")

    cible_id = query.data.replace("regen:", "")
    cible = await services.get_cible_by_id(cible_id)
    nom = cible["nom"] if cible else cible_id

    await query.edit_message_text(f"⚡ Génération en cours pour *{nom}*…", parse_mode="Markdown")

    result = await services.generate_lm_for(cible_id)

    if "error" in result:
        await query.edit_message_text(f"❌ Erreur : {result['error']}")
        return

    lm = result.get("lm_texte", "")
    header = f"✅ *LM générée — {result['nom']}*\n\n"
    full = header + lm
    if len(full) > 4000:
        full = full[:4000] + "\n\\[…tronqué]"

    await query.edit_message_text(
        full,
        reply_markup=keyboard_after_lm(cible_id),
        parse_mode="Markdown",
    )


async def handle_send_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Demande de confirmation avant envoi (callback: send_confirm:<uuid>)."""
    query = update.callback_query
    await query.answer()

    cible_id = query.data.replace("send_confirm:", "")
    cible = await services.get_cible_by_id(cible_id)

    if not cible:
        await query.edit_message_text("❌ Cible introuvable.")
        return

    email = cible.get("email") or "—"
    await query.edit_message_text(
        f"✉️ Confirmer l'envoi ?\n\n*{cible['nom']}*\n📧 {email}",
        reply_markup=keyboard_send_confirm(cible_id),
        parse_mode="Markdown",
    )


async def handle_send_go(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Exécute l'envoi (callback: send_go:<uuid>)."""
    query = update.callback_query
    await query.answer("Envoi en cours…")

    cible_id = query.data.replace("send_go:", "")
    await query.edit_message_text("📤 Envoi en cours…")

    result = await services.send_one(cible_id)

    if "error" in result:
        await query.edit_message_text(f"❌ Erreur : {result['error']}")
    else:
        await query.edit_message_text(
            f"✅ Email envoyé !\n\n*{result['nom']}*\n📧 {result['email']}",
            parse_mode="Markdown",
        )


async def handle_send_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Annule l'envoi (callback: send_cancel)."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Envoi annulé.")


async def handle_back_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retour à la liste (callback: back_list) — ré-exécute la dernière commande /cibles."""
    query = update.callback_query
    await query.answer()

    last_args = context.user_data.get("last_list_args", [])
    # Simule une commande /cibles avec les derniers args
    from app.bot.commands.targets import cmd_cibles

    class _FakeMessage:
        async def reply_text(self, text, **kwargs):
            await query.edit_message_text(text, **kwargs)

    class _FakeUpdate:
        message = _FakeMessage()
        effective_chat = query.message.chat

    class _FakeContext:
        args = last_args
        user_data = context.user_data

    await cmd_cibles(_FakeUpdate(), _FakeContext())
