import os
import json
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from deep_translator import GoogleTranslator

# ==============================
# === Настройки через окружение ===
# ==============================
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")  # токен бота из переменных окружения
if not BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не задан в переменных окружения!")

SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "-1003681531983"))  # MegaGold_Source
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "-1003240723502"))  # MegaGoldRu

CACHE_FILE = "translated_posts.json"  # файл для хранения ID обработанных сообщений

# ==============================
# === Загрузка уже обработанных ID ===
# ==============================
processed_ids = set()
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                processed_ids = set(json.loads(content))
    except json.JSONDecodeError:
        print(f"⚠️ {CACHE_FILE} пустой или повреждён, создаём новый список")
        processed_ids = set()

# ==============================
# === Функция перевода текста ===
# ==============================
def translate_text(text: str) -> str:
    try:
        return GoogleTranslator(source='auto', target='ru').translate(text)
    except Exception as e:
        print(f"❌ Ошибка при переводе: {e}")
        return text

# ==============================
# === Сохранение обработанных ID ===
# ==============================
def save_processed(post_id: int):
    processed_ids.add(post_id)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed_ids), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка при сохранении {CACHE_FILE}: {e}")

# ==============================
# === Обработчик сообщений из канала ===
# ==============================
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        post = update.channel_post
        if not post:
            return

        post_id = post.message_id
        if post_id in processed_ids:
            print(f"⚠️ Сообщение {post_id} уже обработано, пропускаем")
            return

        original_text = post.text or post.caption
        if not original_text:
            print(f"⚠️ Сообщение {post_id} пустое, пропускаем")
            save_processed(post_id)
            return

        print(f"🔔 Новое сообщение из источника ({post_id}): {original_text[:100]}")
        translated = translate_text(original_text)

        await context.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=translated)
        print(f"✅ Сообщение {post_id} переведено и отправлено в целевой канал")

        save_processed(post_id)
        time.sleep(1)  # небольшая пауза между сообщениями

    except Exception as e:
        print(f"❌ Ошибка при обработке сообщения: {e}")

# ==============================
# === Запуск бота ===
# ==============================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_post_handler))

print("🚀 MetalTrans (deep_translator) запущен и готов к переводу новостей")
app.run_polling()
