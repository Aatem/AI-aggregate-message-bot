# бот для агрегации пересланных ему сообщений и извлечения задач через Gemini
import asyncio
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import google.generativeai as gemini


SYSTEM_PROMPT = """Ты менеджер задач. Тебе нужно вычленять из текста задачи и записать их в список задач.
Если в тексте нет задач, просто ответь "Задач нет".
Если задачи есть, запиши их в виде нумерованного списка.
Если в тексте есть дата или время, запиши задачу в формате: "1. [задача] (до [дата/время])".
Если в тексте есть несколько задач, запиши их все.
Если в тексте есть повторяющиеся задачи, запиши их только один раз.
Если в тексте есть задачи с разными датами, запиши их все с соответствующими датами.
Если в тексте есть задачи без даты, запиши их без даты.
Если в тексте есть задачи с датой, но без времени, запиши их с датой.
Если в тексте есть задачи с временем, но без даты, запиши их с временем.
Если в тексте есть задачи с датой и временем, запиши их с датой и временем.
Если в тексте есть задачи с датой и временем в разном формате, запиши их в одном формате.
"""

user_notes = {}
user_tasks = {}


async def send_merged_text(user_id, context: ContextTypes.DEFAULT_TYPE):
    """Собираем заметки, отправляем их в Gemini и выдаём результат"""
    notes = user_notes.get(user_id, [])
    if not notes:
        return

    merged_text = "\n---\n".join(notes)

    try:
        model = gemini.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(f"{SYSTEM_PROMPT}\n\nВот текст заметок:\n{merged_text}")
        tasks_text = response.text.strip() if response.text else "Задачи не найдены."
    except Exception as e:
        tasks_text = f"Ошибка при обработке Gemini: {e}"

    final_message = f"ЗАМЕТКИ:\n{merged_text}\n\nКЛЮЧЕВЫЕ ЗАДАЧИ:\n{tasks_text}"

    await context.bot.send_message(chat_id=user_id, text=final_message)

    user_notes[user_id] = []
    user_tasks.pop(user_id, None)


async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    text = msg.text or msg.caption
    if not text:
        return

    user_id = msg.chat.id
    user_notes.setdefault(user_id, []).append(text)

    if user_id in user_tasks:
        user_tasks[user_id].cancel()

    user_tasks[user_id] = context.application.create_task(timer_send(user_id, context))


async def timer_send(user_id, context):
    try:
        await asyncio.sleep(1.5)  # ждём паузу после последнего сообщения
        await send_merged_text(user_id, context)
    except asyncio.CancelledError:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот активен и готов принимать пересланные сообщения!")


def main():
    TOKEN = "8275396205:AAEMwgFx3jO1Wi3xFEb8Qa-abQUH59DmZfM"        # вставь свой токен Telegram
    GEMINI_API_KEY = "AIzaSyBUp0lsVlCSxs17PdD35IP95MCsnqdLPW0"  # вставь свой ключ Gemini
    PORT = int(os.environ.get("PORT", 8443))  # Render предоставляет порт через переменную окружения
    APP_NAME = os.environ.get("RENDER_SERVICE_NAME")  # Имя сервиса на Render
    
    gemini.configure(api_key=GEMINI_API_KEY)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.FORWARDED & (filters.TEXT | filters.CAPTION), handle_forward))
    
    url = f"https://{APP_NAME}.onrender.com/"
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=url
        )

    
if __name__ == "__main__":
    main()
