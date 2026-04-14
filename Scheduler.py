"""
scheduler.py - المجدول الدوري للمهام التلقائية
"""
import logging
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from telegram.constants import ParseMode
import database as db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Riyadh")


def start_scheduler(app: Application):
    """تشغيل المجدول مع تمرير تطبيق البوت"""

    @scheduler.scheduled_job("cron", hour=8, minute=0)
    async def daily_inventory_check():
        """فحص المخزون يومياً الساعة 8 صباحاً"""
        low_parts = await db.get_low_stock_parts(threshold_multiplier=1.5)
        if not low_parts:
            return

        admin_ids = _get_admin_ids()
        if not admin_ids:
            logger.warning("لا يوجد معرّفات أدمن لإرسال التنبيهات اليومية")
            return

        alert = "🌅 *تقرير المخزون الصباحي*\n\n"
        alert += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
        alert += "القطع التي تحتاج إعادة طلب:\n\n"

        for part in low_parts:
            pct = (float(part['current_stock']) / max(float(part['minimum_threshold']), 0.001)) * 100
            icon = "🔴" if pct <= 50 else "🟡"
            alert += f"{icon} *{part['part_name']}*\n   الرصيد: {float(part['current_stock'])} {part['unit']} ({pct:.0f}% من الحد الأدنى)\n\n"

        for chat_id in admin_ids:
            try:
                await app.bot.send_message(chat_id=chat_id, text=alert, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"فشل إرسال تنبيه الأدمن {chat_id}: {e}")

    @scheduler.scheduled_job("cron", day_of_week="mon", hour=9, minute=0)
    async def weekly_maintenance_summary():
        """ملخص أسبوعي كل اثنين"""
        from database import get_pool
        pool = await get_pool()

        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN maintenance_type = 'علاجية' THEN 1 ELSE 0 END) as corrective,
                    SUM(CASE WHEN maintenance_type = 'وقائية' THEN 1 ELSE 0 END) as preventive,
                    SUM(CASE WHEN maintenance_type = 'طارئة' THEN 1 ELSE 0 END) as emergency,
                    ROUND(AVG(repair_hours)::numeric, 2) as avg_hours,
                    COUNT(DISTINCT machine_name) as machines_count
                FROM maintenance_records
                WHERE created_at >= NOW() - INTERVAL '7 days'
            """)

        if not stats or stats['total'] == 0:
            return

        summary = (
            "📊 *ملخص الصيانة الأسبوعي*\n\n"
            f"📅 الأسبوع المنتهي: {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"📋 إجمالي السجلات: *{stats['total']}*\n"
            f"🔧 صيانة علاجية: {stats['corrective']}\n"
            f"✅ صيانة وقائية: {stats['preventive']}\n"
            f"🚨 حالات طارئة: {stats['emergency']}\n"
            f"⏱ متوسط وقت الإصلاح: {stats['avg_hours']} ساعة\n"
            f"🏭 عدد الماكينات: {stats['machines_count']}"
        )

        admin_ids = _get_admin_ids()
        for chat_id in admin_ids:
            try:
                await app.bot.send_message(chat_id=chat_id, text=summary, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"فشل إرسال الملخص الأسبوعي: {e}")

    scheduler.start()
    logger.info("✅ المجدول يعمل (فحص يومي 8ص + ملخص أسبوعي الإثنين 9ص)")


def _get_admin_ids() -> list:
    """جلب معرّفات المدراء من متغيرات البيئة"""
    ids_str = os.environ.get("ADMIN_CHAT_IDS", "")
    if not ids_str:
        return []
    try:
        return [int(x.strip()) for x in ids_str.split(",") if x.strip()]
    except ValueError:
        return []
