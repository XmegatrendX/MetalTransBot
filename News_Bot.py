import os
import json
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from deep_translator import GoogleTranslator
from fastapi import FastAPI, Request, HTTPException
import uvicorn

# ==============================
# === Настройки через окружение ===
# ==============================
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не задан в переменных окружения!")

SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "-1003681531983"))
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "-1003240723502"))

CACHE_FILE = "translated_posts.json"

PORT = int(os.environ.get("PORT", 10000))

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("❌ Укажите WEBHOOK_URL без /webhook в конце (например https://metaltransbot.onrender.com)")

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
        print(f"⚠️ {CACHE_FILE} повреждён — начинаем с чистого листа")

def save_processed(post_id: int):
    processed_ids.add(post_id)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed_ids), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка сохранения кэша: {e}")

# ==============================
# === Перевод текста ===
# ==============================
def translate_text(text: str) -> str:
    try:
        return GoogleTranslator(source='auto', target='ru').translate(text)
    except Exception as e:
        print(f"❌ Ошибка перевода: {e}")
        return text

# ==============================
# === Обработчик новых постов из канала ===
# ==============================
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        post = update.channel_post
        if not post:
            return

        post_id = post.message_id
        if post_id in processed_ids:
            print(f"⚠️ Сообщение {post_id} уже обработано")
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
        time.sleep(1)  # защита от флуда
    except Exception as e:
        print(f"❌ Ошибка при обработке сообщения: {e}")

# ==============================
# === Создание Telegram Application ===
# ==============================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_post_handler))

# ==============================
# === Установка webhook при старте ===
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
            print("✅ Webhook уже правильный")
    except Exception as e:
        print(f"❌ Ошибка установки webhook: {e}")

# ==============================
# === FastAPI приложение ===
# ==============================
fastapi_app = FastAPI()

# Health check (для Render)
@fastapi_app.get("/")
async def root():
    return {"status": "ok", "message": "MetalTrans bot is alive and running with webhooks"}

# Webhook-эндпоинт от Telegram
@fastapi_app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, app.bot)

        # Ключевое исправление: инициализация Application перед каждым обновлением
        await app.initialize()
        await app.process_update(update)
        # await app.shutdown()  # опционально, можно раскомментировать при проблемах с памятью

        return {"ok": True}
    except Exception as e:
        print(f"❌ Ошибка webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Установка webhook при запуске сервера
async def startup_event():
    await set_webhook()
    print("🚀 Бот полностью готов к работе в webhook-режиме")

fastapi_app.add_event_handler("startup", startup_event)

# ==============================
# === Запуск сервера ===
# ==============================
if __name__ == "__main__":
    print("Запускаем сервер на Render...")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT)
