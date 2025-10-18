import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)

load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN")
ADMIN_ID    = int(os.getenv("ADMIN_CHAT_ID", "0"))  # 0 = вимкнено
COURSE_LINK = os.getenv("COURSE_LINK", "https://t.me/+e8AkbgxD9-tjMTEy")
PRICE_UAH   = int(os.getenv("PRICE_UAH", "799"))
CARD_NUMBER = os.getenv("CARD_NUMBER", "4441111063197051")

# Шаблонні питання (кнопки). Можеш додати свої.
FAQ_QUESTIONS = [
    "Що входить у курс?",
    "Для кого підходить Dyson WOW-укладка?",
    "Скільки триває доступ до матеріалів?",
    "Чи підходить новачкам?",
    "Чи буде підтримка/чат?",
]

# Простий антиспам/тротлінг (1 видача лінку раз на 2 хв на користувача)
LINK_COOLDOWN = timedelta(minutes=2)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("💬 Про курс"), KeyboardButton(f"💳 Оплатити {PRICE_UAH} грн")],
            [KeyboardButton("🧾 Надіслати чек"), KeyboardButton("🔗 Отримати посилання")],
            [KeyboardButton("❓ Питання за шаблоном")],
        ],
        resize_keyboard=True
    )


def faq_inline_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(q, callback_data=f"faq::{q}")] for q in FAQ_QUESTIONS]
    buttons.append([InlineKeyboardButton("◀️ Назад до меню", callback_data="back_menu")])
    return InlineKeyboardMarkup(buttons)


def greeting_text(first_name: str) -> str:
    return (
        f"Привіт, {first_name or 'друже'}! 👋\n\n"
        "Цікавить мій курс **WOW-укладка на Dyson**?\n"
        "Обери дію нижче або напиши повідомлення — я відповім автоматично."
    )


async def notify_admin(ctx: ContextTypes.DEFAULT_TYPE, text: str, update: Update):
    if ADMIN_ID > 0:
        try:
            user = update.effective_user
            uname = f"@{user.username}" if user and user.username else ""
            await ctx.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📩 Нове звернення від {user.id} {uname}\n\n{text}"
            )
        except Exception:
            pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(greeting_text(update.effective_user.first_name), reply_markup=main_keyboard())


async def about_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔥 **WOW-укладка на Dyson** — короткий, практичний курс:\n"
        "• як зробити живий прикореневий об’єм;\n"
        "• техніка стійких та об’ємних локонів;\n"
        "• догляд і підготовка волосся;\n"
        "• секрети стайлінгу для довгої фіксації.\n\n"
        "Готова/ий? Обери «Оплатити» або «Надіслати чек» — і я відкрию доступ 😉"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard())


async def pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"💳 *Оплата курсу*: **{PRICE_UAH} грн**\n"
        f"Надішли на картку: `{CARD_NUMBER}`\n\n"
        "Після оплати натисни «🧾 Надіслати чек» та прикріпи скрін/фото квитанції.\n"
        "Я перевірю і відправлю посилання на курс."
    )
    await update.message.reply_text(text, reply_markup=main_keyboard(), parse_mode="Markdown")


async def ask_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_receipt"] = True
    await update.message.reply_text(
        "Будь ласка, прикріпи *фото/скрін/файл* з квитанцією 🧾\n"
        "Як тільки отримаю — одразу надішлю посилання на курс.",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )


async def send_course_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Тротлінг: не частіше ніж раз у LINK_COOLDOWN
    now = datetime.utcnow()
    last = context.user_data.get("last_link_time")
    if last and now - last < LINK_COOLDOWN:
        wait_s = int((LINK_COOLDOWN - (now - last)).total_seconds())
        return await update.message.reply_text(
            f"Щойно надсилав посилання. Будь ласка, зачекай {wait_s} сек і натисни ще раз 🙌",
            reply_markup=main_keyboard()
        )
    context.user_data["last_link_time"] = now
    await update.message.reply_text(
        f"🔗 **Посилання на курс:**\n{COURSE_LINK}\n\nПриємного навчання! 💫",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )


async def handle_receipt_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Приймає фото/документ як чек.
    Якщо користувач раніше натиснув «Надіслати чек» — одразу видаємо лінк.
    Інакше теж приймемо як чек (менш строгий сценарій).
    """
    context.user_data["awaiting_receipt"] = False
    # (опційно) переслати адміну
    await notify_admin(context, "Надіслано чек (фото/документ).", update)

    # Видаємо лінк
    await update.effective_message.reply_text("Дякую! Перевірив ✅")
    await send_course_link(update, context)


async def template_questions_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Ось популярні запитання. Обери — і я відповім:"
    await update.message.reply_text(text, reply_markup=faq_inline_keyboard())


async def on_faq_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_menu":
        await query.edit_message_text("Повернув у меню. Обирай дію нижче 👇")
        await query.message.reply_text("Меню:", reply_markup=main_keyboard())
        return

    if data.startswith("faq::"):
        q = data.split("faq::", 1)[1]
        # Відповіді на шаблонні питання (конфігуруй під себе)
        answers = {
            "Що входить у курс?":
                "Короткі відео-уроки, гайди з догляду, покрокові техніки об’єму й локонів, список інструментів і продуктів.",
            "Для кого підходить Dyson WOW-укладка?":
                "Для новачків і тих, хто вже має Dyson. Навчишся робити укладку швидко й стійко без зайвих зусиль.",
            "Скільки триває доступ до матеріалів?":
                "Доступ відкривається одразу після підтвердження оплати. Формат — Telegram-канал із матеріалами.",
            "Чи підходить новачкам?":
                "Так, уся структура зроблена просто: 1) підготовка волосся; 2) базові техніки; 3) секрети фіксації.",
            "Чи буде підтримка/чат?":
                "Так, будуть підказки в каналі й відповіді на популярні питання, а також оновлення матеріалів.",
        }
        answer = answers.get(q, "Зараз відповім…")
        text = f"*Питання:*\n{q}\n\n*Відповідь:*\n{answer}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=faq_inline_keyboard())


async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text or ""
    # Тригерні кнопки за текстом
    if "про курс" in msg.lower():
        return await about_course(update, context)
    if "оплатити" in msg.lower():
        return await pay_info(update, context)
    if "чек" in msg.lower():
        return await ask_receipt(update, context)
    if "посилання" in msg.lower():
        return await send_course_link(update, context)

    # За замовчуванням: чемна відповідь + меню
    await update.message.reply_text(
        "Я з тобою на зв’язку. Обери дію в меню або напиши, чим допомогти 🙌",
        reply_markup=main_keyboard()
    )
    # (опційно) сповіщення адміну
    await notify_admin(context, f"Повідомлення від користувача: {msg}", update)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не заданий у .env")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_faq_click))
    # Кнопки/команди
    app.add_handler(MessageHandler(filters.Regex("^💬 Про курс$"), about_course))
    app.add_handler(MessageHandler(filters.Regex(f"^💳 Оплатити {PRICE_UAH} грн$"), pay_info))
    app.add_handler(MessageHandler(filters.Regex("^🧾 Надіслати чек$"), ask_receipt))
    app.add_handler(MessageHandler(filters.Regex("^🔗 Отримати посилання$"), send_course_link))
    app.add_handler(MessageHandler(filters.Regex("^❓ Питання за шаблоном$"), template_questions_entry))

    # Прийом чека: фото, файл, відео (на випадок екранки)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO, handle_receipt_any))

    # Будь-який інший текст
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
