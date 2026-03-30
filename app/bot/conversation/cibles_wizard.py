"""
Wizard /cibles — flow guidé par boutons inline.
Étapes : statut → secteur → département → résultats
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler,
)

from app.bot.auth import require_authorized
from app.bot import services
from app.bot.ui import STATUT_EMOJI, SECTEUR_EMOJI, format_cible_card, keyboard_cible_actions

CL_STATUT  = 20
CL_SECTEUR = 21
CL_DEPT    = 22

DEPTS = ["75", "77", "78", "91", "92", "93", "94", "95"]


def _kb_statut() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🆕 Neuf",   callback_data="cl_stat:neuf"),
            InlineKeyboardButton("✅ Prêt",   callback_data="cl_stat:prêt"),
        ],
        [
            InlineKeyboardButton("📤 Envoyé", callback_data="cl_stat:envoyé"),
            InlineKeyboardButton("❌ Erreur", callback_data="cl_stat:erreur"),
        ],
        [InlineKeyboardButton("🔀 Tous les statuts", callback_data="cl_stat:tous")],
    ])


def _kb_secteur() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏛️ Mairies",   callback_data="cl_sect:mairies"),
            InlineKeyboardButton("🎓 Éducation", callback_data="cl_sect:education"),
        ],
        [InlineKeyboardButton("🔀 Tous les secteurs", callback_data="cl_sect:tous")],
    ])


def _kb_dept() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for d in DEPTS:
        row.append(InlineKeyboardButton(d, callback_data=f"cl_dept:{d}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🔀 Tous les départements", callback_data="cl_dept:tous")])
    return InlineKeyboardMarkup(rows)


@require_authorized
async def cibles_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["cl"] = {}
    await update.message.reply_text(
        "📋 *Rechercher des cibles*\n\nÉtape 1/3 — Quel statut ?",
        reply_markup=_kb_statut(),
        parse_mode="Markdown",
    )
    return CL_STATUT


async def cibles_statut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    val = query.data.replace("cl_stat:", "")
    context.user_data["cl"]["statut"] = None if val == "tous" else val
    label = f"🔀 Tous" if val == "tous" else f"{STATUT_EMOJI.get(val, '')} {val}"
    await query.edit_message_text(
        f"📋 *Rechercher des cibles*\n\n✔️ Statut : {label}\n\nÉtape 2/3 — Quel secteur ?",
        reply_markup=_kb_secteur(),
        parse_mode="Markdown",
    )
    return CL_SECTEUR


async def cibles_secteur(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    val = query.data.replace("cl_sect:", "")
    context.user_data["cl"]["secteur"] = None if val == "tous" else val
    statut = context.user_data["cl"].get("statut") or "tous"
    label_stat = f"{STATUT_EMOJI.get(statut, '🔀')} {statut}"
    label_sect = f"🔀 Tous" if val == "tous" else f"{SECTEUR_EMOJI.get(val, '')} {val}"
    await query.edit_message_text(
        f"📋 *Rechercher des cibles*\n\n"
        f"✔️ Statut : {label_stat}\n"
        f"✔️ Secteur : {label_sect}\n\n"
        f"Étape 3/3 — Quel département ?",
        reply_markup=_kb_dept(),
        parse_mode="Markdown",
    )
    return CL_DEPT


async def cibles_dept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    val = query.data.replace("cl_dept:", "")
    cl = context.user_data["cl"]
    cl["dept"] = None if val == "tous" else val

    statut  = cl.get("statut")
    secteur = cl.get("secteur")
    dept    = cl.get("dept")

    try:
        cibles = await services.list_cibles(
            statut=statut, secteur=secteur, departement=dept, limit=15
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Erreur : {e}")
        return ConversationHandler.END

    # Résumé des filtres
    parts = []
    if statut:  parts.append(f"{STATUT_EMOJI.get(statut, '')} {statut}")
    else:       parts.append("🔀 tous statuts")
    if secteur: parts.append(f"{SECTEUR_EMOJI.get(secteur, '')} {secteur}")
    else:       parts.append("🔀 tous secteurs")
    if dept:    parts.append(f"📍 dept {dept}")
    else:       parts.append("📍 tous depts")
    filtre = "  ·  ".join(parts)

    # Sauvegarde pour "retour liste"
    context.user_data["last_list_args"] = [
        statut or "tous", secteur or "tous", dept or "tous"
    ]

    if not cibles:
        await query.edit_message_text(
            f"📋 *{filtre}*\n\nAucune cible trouvée.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    header = f"📋 *{filtre}* — {len(cibles)} résultat(s)"
    keyboard = []
    for c in cibles:
        email_icon = " 📧" if c.get("email") else " ✗"
        dept_label = f" [{c.get('departement', '?')}]" if not dept else ""
        label = f"{SECTEUR_EMOJI.get(c['secteur'], '•')} {c['nom'][:30]}{dept_label}{email_icon}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"detail:{c['id']}")])

    await query.edit_message_text(
        header,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Recherche annulée.")
    return ConversationHandler.END


def build_cibles_wizard() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("cibles", cibles_start)],
        states={
            CL_STATUT:  [CallbackQueryHandler(cibles_statut,  pattern=r"^cl_stat:")],
            CL_SECTEUR: [CallbackQueryHandler(cibles_secteur, pattern=r"^cl_sect:")],
            CL_DEPT:    [CallbackQueryHandler(cibles_dept,    pattern=r"^cl_dept:")],
        },
        fallbacks=[CommandHandler("annuler", cancel_wizard)],
    )
