"""
Wizard /generer_batch — flow guidé par boutons inline.
Étapes : secteur → département → nombre (ou Entrée direct)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters,
)

from app.bot.auth import require_authorized
from app.bot import services
from app.bot.ui import SECTEUR_EMOJI

GB_SECTEUR = 30
GB_DEPT    = 31
GB_LIMIT   = 32

DEPTS = ["75", "77", "78", "91", "92", "93", "94", "95"]


def _kb_secteur() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏛️ Mairies",   callback_data="gb_sect:mairies"),
            InlineKeyboardButton("🎓 Éducation", callback_data="gb_sect:education"),
        ],
        [InlineKeyboardButton("🔀 Les deux secteurs", callback_data="gb_sect:tous")],
    ])


def _kb_dept() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for d in DEPTS:
        row.append(InlineKeyboardButton(d, callback_data=f"gb_dept:{d}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🔀 Tous les départements", callback_data="gb_dept:tous")])
    return InlineKeyboardMarkup(rows)


def _kb_limit() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10",  callback_data="gb_limit:10"),
            InlineKeyboardButton("20",  callback_data="gb_limit:20"),
            InlineKeyboardButton("50",  callback_data="gb_limit:50"),
        ],
        [InlineKeyboardButton("▶️ Lancer avec 10 (défaut)", callback_data="gb_limit:10")],
    ])


@require_authorized
async def generer_batch_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["gb"] = {}
    await update.message.reply_text(
        "⚡ *Générer des LM en masse*\n\nÉtape 1/3 — Quel secteur ?",
        reply_markup=_kb_secteur(),
        parse_mode="Markdown",
    )
    return GB_SECTEUR


async def gb_secteur(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    val = query.data.replace("gb_sect:", "")
    context.user_data["gb"]["secteur"] = None if val == "tous" else val
    label = f"🔀 Les deux" if val == "tous" else f"{SECTEUR_EMOJI.get(val, '')} {val}"
    await query.edit_message_text(
        f"⚡ *Générer des LM en masse*\n\n✔️ Secteur : {label}\n\nÉtape 2/3 — Quel département ?",
        reply_markup=_kb_dept(),
        parse_mode="Markdown",
    )
    return GB_DEPT


async def gb_dept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    val = query.data.replace("gb_dept:", "")
    gb = context.user_data["gb"]
    gb["dept"] = None if val == "tous" else val

    secteur = gb.get("secteur")
    label_sect = f"🔀 Les deux" if not secteur else f"{SECTEUR_EMOJI.get(secteur, '')} {secteur}"
    label_dept = f"📍 Dept {val}" if val != "tous" else "📍 Tous les depts"

    await query.edit_message_text(
        f"⚡ *Générer des LM en masse*\n\n"
        f"✔️ Secteur : {label_sect}\n"
        f"✔️ Dept    : {label_dept}\n\n"
        f"Étape 3/3 — Combien de LM ?\n"
        f"_(Clique ou tape un nombre)_",
        reply_markup=_kb_limit(),
        parse_mode="Markdown",
    )
    return GB_LIMIT


async def gb_limit_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Choix du limit via bouton."""
    query = update.callback_query
    await query.answer()
    limit = int(query.data.replace("gb_limit:", ""))
    await query.edit_message_text(
        f"⚡ Génération en cours (max {limit})…"
    )
    return await _execute(query.edit_message_text, context, limit)


async def gb_limit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Choix du limit via saisie texte libre."""
    text = update.message.text.strip()
    try:
        limit = int(text)
        if limit < 1 or limit > 200:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Entrez un nombre entre 1 et 200.")
        return GB_LIMIT

    msg = await update.message.reply_text(f"⚡ Génération en cours (max {limit})…")
    return await _execute(msg.edit_text, context, limit)


async def _execute(edit_fn, context: ContextTypes.DEFAULT_TYPE, limit: int) -> int:
    gb = context.user_data.get("gb", {})
    secteur = gb.get("secteur")
    dept    = gb.get("dept")

    try:
        result = await services.generate_batch(limit=limit, departement=dept, secteur=secteur)
    except Exception as e:
        await edit_fn(f"❌ Erreur : {e}")
        return ConversationHandler.END

    generees   = result.get("generees", 0)
    nb_erreurs = len(result.get("erreurs", []))

    # Résumé des filtres appliqués
    parts = []
    if secteur: parts.append(f"{SECTEUR_EMOJI.get(secteur, '')} {secteur}")
    else:       parts.append("🔀 tous secteurs")
    if dept:    parts.append(f"📍 dept {dept}")
    else:       parts.append("📍 tous depts")
    filtre = "  ·  ".join(parts)

    lines = [
        f"✅ *Génération terminée*",
        f"_{filtre}_",
        f"",
        f"  📝 Générées : {generees}",
        f"  ❌ Erreurs  : {nb_erreurs}",
    ]
    if result.get("erreurs"):
        lines.append("\n⚠️ *Erreurs :*")
        for err in result["erreurs"][:5]:
            lines.append(f"  • {err}")
    if generees > 0:
        lines.append(f"\n💡 {generees} LM prêtes — /envoyer\\_tous pour lancer l'envoi")

    await edit_fn("\n".join(lines), parse_mode="Markdown")
    return ConversationHandler.END


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Génération annulée.")
    return ConversationHandler.END


def build_generer_wizard() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("generer_batch", generer_batch_start)],
        states={
            GB_SECTEUR: [CallbackQueryHandler(gb_secteur,    pattern=r"^gb_sect:")],
            GB_DEPT:    [CallbackQueryHandler(gb_dept,       pattern=r"^gb_dept:")],
            GB_LIMIT:   [
                CallbackQueryHandler(gb_limit_btn,  pattern=r"^gb_limit:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, gb_limit_text),
            ],
        },
        fallbacks=[CommandHandler("annuler", cancel_wizard)],
    )
