from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from deep_translator import GoogleTranslator
import json
import os
import time

# === Настройки ===
BOT_TOKEN = "8487024740:AAFMAjfWccoD1kEdAdFustW632iGWZsbAHE"  # токен бота
SOURCE_CHANNEL_ID = -1003681531983   # MegaGold_Source
TARGET_CHANNEL_ID = -1003240723502   # MegaGoldRu

# === Файл для хранения ID уже обработанных сообщений ===
CACHE_FILE = "translated_posts.json"
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        processed_ids = set(json.load(f))
else:
    processed_ids = set()

# Функция перевода текста через deep_translator
def translate_text(text):
    try:
        translated = GoogleTranslator(source='auto', target='ru').translate(text)
        return translated
    except Exception as e:
        print(f"❌ Ошибка при переводе: {e}")
        return text

# Сохраняем ID сообщения в файл
def save_processed(post_id):
    processed_ids.add(post_id)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(processed_ids), f, ensure_ascii=False, indent=2)

# Обработчик сообщений из канала
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
        time.sleep(1)

    except Exception as e:
        print(f"❌ Ошибка при обработке сообщения: {e}")

# === Запуск бота ===
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_post_handler))

print("🚀 MetalTrans (deep_translator) запущен и готов к переводу новостей")
app.run_polling()
