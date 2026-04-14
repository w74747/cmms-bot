"""
CMMS Telegram Bot - Main Entry Point
نظام إدارة الصيانة الذكي عبر تيليجرام
"""
import asyncio
import logging
import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from handlers import (
    handle_photo, handle_text, handle_voice,
    handle_start, handle_help, handle_report,
    handle_inventory, handle_insights
)
from database import init_db
from scheduler import start_scheduler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    """تشغيل البوت الرئيسي"""
    await init_db()
    logger.info("✅ قاعدة البيانات جاهزة")

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # أوامر البوت
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("report", handle_report))
    app.add_handler(CommandHandler("inventory", handle_inventory))
    app.add_handler(CommandHandler("insights", handle_insights))

    # معالجة الرسائل
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # تشغيل المجدول
    start_scheduler(app)

    logger.info("🤖 البوت يعمل الآن...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
