"""Commandes /stats et /pipeline."""
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.auth import require_authorized
from app.bot import services
from app.bot.ui import STATUT_EMOJI, progress_bar


@require_authorized
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tableau de bord des candidatures spontanées."""
    try:
        s = await services.get_stats()
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur : {e}")
        return

    total = s.get("total", 0)
    neuf    = s.get("neuf", 0)
    pret    = s.get("prêt", 0)
    envoye  = s.get("envoyé", 0)
    erreur  = s.get("erreur", 0)

    # Barre de progression globale
    bar_envoye = progress_bar(envoye, total) if total else "—"
    pct = f"{round(envoye / total * 100)}%" if total else "0%"

    par_secteur = s.get("par_secteur", {})
    sect_lines = "  ".join(
        f"🏛️ mairies: {par_secteur.get('mairies', 0)}  🎓 éduc: {par_secteur.get('education', 0)}"
        .split()
    )

    sans_email = s.get("sans_email", 0)

    lines = [
        "📊 *Candidatures spontanées*",
        "─────────────────────",
        f"🆕 Neuf      : {neuf}",
        f"✅ Prêt      : {pret}",
        f"📤 Envoyé    : {envoye}",
        f"❌ Erreur    : {erreur}",
        f"📧 Total     : {total}  _(avec email)_",
        f"🚫 Sans email : {sans_email}  _(ignorés)_",
        "─────────────────────",
        f"Progression : {bar_envoye} {pct}",
        f"🏛️ Mairies : {par_secteur.get('mairies', 0)}   🎓 Éduc : {par_secteur.get('education', 0)}",
    ]

    if pret > 0:
        lines.append(f"\n💡 {pret} cible(s) prête(s) — /envoyer\\_tous pour lancer l'envoi")
    if neuf > 0:
        lines.append(f"💡 {neuf} cible(s) sans LM — /generer\\_batch pour générer")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@require_authorized
async def cmd_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Aperçu des candidatures classiques par statut."""
    try:
        s = await services.get_pipeline()
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur : {e}")
        return

    total = s.pop("total", 0)
    lines = ["📋 *Candidatures classiques*", "─────────────────────"]
    for statut, count in sorted(s.items()):
        emoji = STATUT_EMOJI.get(statut, "•")
        lines.append(f"{emoji} {statut:<12} : {count}")
    lines += ["─────────────────────", f"📦 Total        : {total}"]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
