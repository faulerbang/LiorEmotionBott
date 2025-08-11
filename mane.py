import os, json, logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
AUTO_MODE = os.getenv("AUTO_MODE", "off").lower() == "on"

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "Ты ассистент, который мягко анализирует эмоциональный тон сообщений в диалоге пары. "
    "Отвечай только JSON без лишнего текста. "
    "Поля: tone (одно из: 'поддержка','эмпатия','нейтрально','закрытость','защита','нападение','избегание'), "
    "advice (краткий совет до 20 слов, мягкий и не осуждающий). "
    "Дай безопасный и бережный ответ."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "Привет! Я Lior Emotion Bot.\n"
        "Добавьте меня в общий чат и (по желанию) отключите privacy у BotFather, "
        "чтобы я видел все сообщения (/setprivacy → Disable).\n"
        "Команды:\n"
        "• /analyze <текст> — проанализировать тон\n"
        "• /auto_on и /auto_off — включить/выключить авто-анализ всех сообщений"
    )
    await update.message.reply_text(txt)

async def auto_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    os.environ["AUTO_MODE"] = "on"
    await update.message.reply_text("Авто‑режим включён. Я буду мягко комментировать сообщения чата.")

async def auto_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    os.environ["AUTO_MODE"] = "off"
    await update.message.reply_text("Авто‑режим выключен.")

def want_reply(update: Update) -> bool:
    # В группах отвечаем либо при AUTO_MODE, либо если упомянули бота, либо команда
    chat_type = update.message.chat.type
    if chat_type in ("group", "supergroup"):
        mentioned = update.message.entities and any(e.type == "mention" for e in update.message.entities)
        return AUTO_MODE or mentioned
    return True  # в личке — всегда

def build_messages(text: str):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
         "content": f"Проанализируй это сообщение с точки зрения эмоционального тона и дай JSON: {text}"},
    ]

async def analyze_text(text: str) -> str:
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=build_messages(text),
            temperature=0.2,
        )
        content = resp.choices[0].message.content.strip()
        data = json.loads(content)
        tone = data.get("tone", "нейтрально")
        advice = data.get("advice", "")
        return f"Тон: {tone}\nСовет: {advice}"
    except Exception as e:
        logger.exception("LLM error")
        return "Не смог(ла) проанализировать сейчас, попробуй ещё раз позже."

async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else (update.message.text or "")
    if not text:
        await update.message.reply_text("Пришли текст: /analyze я чувствую злость, но молчу…")
        return
    reply = await analyze_text(text)
    await update.message.reply_text(reply)

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not want_reply(update):
        return
    text = update.message.text or ""
    if not text.strip():
        return
    reply = await analyze_text(text)
    await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("auto_on", auto_on))
    app.add_handler(CommandHandler("auto_off", auto_off))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
