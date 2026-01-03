import os
import json
import time
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from deep_translator import GoogleTranslator
from fastapi import FastAPI, Request, HTTPException
import uvicorn

# ==============================
# === Настройки через окружение ===
# ==============================
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не задан в переменных окружения!")

SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "-1003681531983"))  # MegaGold_Source
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "-1003240723502"))  # MegaGoldRu

CACHE_FILE = "translated_posts.json"

# Порт от Render
PORT = int(os.environ.get("PORT", 10000))

# URL вашего сервиса на Render (обязательно укажите в Environment Variables)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("❌ Укажите WEBHOOK_URL в environment variables (например https://your-service.onrender.com/webhook)")

WEBHOOK_PATH = "/webhook"
FULL_WEBHOOK_URL = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH

# ==============================
# === Кэш обработанных сообщений ===
# ==============================
processed_ids = set()
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                processed_ids = set(json.loads(content))
    except json.JSONDecodeError:
        print(f"⚠️ {CACHE_FILE} повреждён или пустой — начинаем с чистого листа")

def save_processed(post_id: int):
    processed_ids.add(post_id)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed_ids), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка при сохранении кэша: {e}")

# ==============================
# === Функция перевода ===
# ==============================
def translate_text(text: str) -> str:
    try:
        return GoogleTranslator(source='auto', target='ru').translate(text)
    except Exception as e:
        print(f"❌ Ошибка перевода: {e}")
        return text  # возвращаем оригинал при ошибке

# ==============================
# === Обработчик постов из канала ===
# ==============================
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        post = update.channel_post
        if not post:
            return

        post_id = post.message_id
        if post_id in processed_ids:
            print(f"⚠️ Сообщение {post_id} уже обработано — пропускаем")
            return

        original_text = post.text or post.caption or ""
        if not original_text.strip():
            print(f"⚠️ Сообщение {post_id} без текста — пропускаем")
            save_processed(post_id)
            return

        print(f"🔔 Новое сообщение ({post_id}): {original_text[:100]}...")
        translated = translate_text(original_text)

        await context.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=translated)
        print(f"✅ Переведено и отправлено в целевой канал")
        save_processed(post_id)
        time.sleep(1)  # пауза от флуда
    except Exception as e:
        print(f"❌ Ошибка при обработке сообщения: {e}")

# ==============================
# === Telegram Application ===
# ==============================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_post_handler))

# ==============================
# === Установка webhook ===
# ==============================
async def set_webhook():
    try:
        current = await app.bot.get_webhook_info()
        if current.url != FULL_WEBHOOK_URL:
            print(f"Устанавливаем webhook: {FULL_WEBHOOK_URL}")
            success = await app.bot.set_webhook(url=FULL_WEBHOOK_URL)
            if success:
                print("✅ Webhook успешно установлен")
            else:
                print("❌ Не удалось установить webhook")
        else:
            print("✅ Webhook уже установлен правильно")
    except Exception as e:
        print(f"❌ Ошибка при установке webhook: {e}")

# ==============================
# === FastAPI приложение ===
# ==============================
fastapi_app = FastAPI()

# Health check для Render
@fastapi_app.get("/")
async def root():
    return {"status": "ok", "message": "Telegram webhook bot is running"}

# Webhook от Telegram
@fastapi_app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, app.bot)
        await app.process_update(update)
        return {"ok": True}
    except Exception as e:
        print(f"❌ Ошибка в webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Установка webhook при старте сервера
async def startup_event():
    await set_webhook()
    print("🚀 Бот полностью готов к работе в режиме webhook")

fastapi_app.add_event_handler("startup", startup_event)

# ==============================
# === Запуск сервера ===
# ==============================
if __name__ == "__main__":
    print("Запускаем FastAPI + Uvicorn сервер на Render...")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT)
