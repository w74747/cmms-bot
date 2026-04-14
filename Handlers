"""
handlers.py - معالجات رسائل البوت
"""
import io
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import database as db
import ai_processor as ai

logger = logging.getLogger(__name__)

ADMIN_CHAT_IDS = []  # يمكن تعبئتها من متغير بيئة


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    text = (
        "🔧 *مرحباً بك في نظام CMMS الذكي*\n\n"
        "أنا مساعدك الذكي لإدارة الصيانة الصناعية.\n\n"
        "*ما يمكنني فعله:*\n"
        "📸 تحليل صور تقارير الصيانة\n"
        "✍️ استقبال بيانات الصيانة نصياً\n"
        "🎤 معالجة الرسائل الصوتية\n"
        "📦 تتبع المخزون وإرسال التنبيهات\n"
        "📊 تحليل الأعطال المتكررة\n\n"
        "*الأوامر المتاحة:*\n"
        "/report - آخر تقارير الصيانة\n"
        "/inventory - حالة المخزون\n"
        "/insights - تحليل ماكينة محددة\n"
        "/help - المساعدة\n\n"
        "ابدأ بإرسال صورة ورقة الصيانة! 👇"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة المساعدة"""
    text = (
        "📖 *دليل الاستخدام*\n\n"
        "*إضافة سجل صيانة:*\n"
        "• أرسل صورة ورقة الصيانة → يستخرج البيانات تلقائياً\n"
        "• أو اكتب: `صيانة ماكينة الضغط، تغيير زيت، 2 ساعة`\n\n"
        "*عرض التقارير:*\n"
        "`/report` - آخر 10 سجلات\n"
        "`/report 20` - آخر 20 سجل\n\n"
        "*المخزون:*\n"
        "`/inventory` - عرض المخزون\n"
        "`/inventory add زيت هيدروليك 10 لتر` - إضافة مخزون\n\n"
        "*تحليل الماكينات:*\n"
        "`/insights ماكينة الضغط` - تحليل ماكينة محددة\n"
        "`/insights ماكينة الضغط 60` - تحليل آخر 60 يوم\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة صور تقارير الصيانة"""
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("⏳ جاري تحليل الصورة...")

    try:
        # جلب أعلى جودة للصورة
        photo = update.message.photo[-1]
        file_id = photo.file_id
        file = await context.bot.get_file(file_id)

        # تحميل الصورة
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        image_bytes = buf.getvalue()

        await msg.edit_text("🔍 يتم استخراج البيانات بالذكاء الاصطناعي...")

        # استخراج البيانات
        extracted = await ai.extract_from_image(image_bytes)

        if "error" in extracted:
            await msg.edit_text(f"❌ {extracted['error']}")
            return

        # حفظ في قاعدة البيانات
        record_id = await db.save_maintenance_record(extracted, chat_id, file_id)

        # تجهيز رسالة التأكيد
        confirmation = _format_confirmation(extracted, record_id)
        await msg.edit_text(confirmation, parse_mode=ParseMode.MARKDOWN)

        # التحقق من المخزون
        await _check_and_notify_inventory(update, context)

        # التحقق من الأعطال المتكررة
        await _check_recurring_faults(update, context, extracted.get("machine_name", ""))

    except Exception as e:
        logger.error(f"خطأ في معالجة الصورة: {e}")
        await msg.edit_text(f"❌ حدث خطأ أثناء المعالجة: {str(e)}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # تجاهل الرسائل القصيرة جداً
    if len(text) < 10:
        await update.message.reply_text(
            "💡 أرسل وصفاً للصيانة أو صورة ورقة الصيانة.\n"
            "مثال: `صيانة ماكينة X، تغيير بلف رقم 3، استغرق ساعتين`"
        )
        return

    msg = await update.message.reply_text("⏳ جاري تحليل النص...")

    try:
        extracted = await ai.extract_from_text(text)

        if "error" in extracted:
            await msg.edit_text(
                f"ℹ️ {extracted['error']}\n\n"
                "💡 تأكد من ذكر: اسم الماكينة، العمل المنفذ، والوقت المستغرق."
            )
            return

        record_id = await db.save_maintenance_record(extracted, chat_id)
        confirmation = _format_confirmation(extracted, record_id)
        await msg.edit_text(confirmation, parse_mode=ParseMode.MARKDOWN)

        await _check_and_notify_inventory(update, context)
        await _check_recurring_faults(update, context, extracted.get("machine_name", ""))

    except Exception as e:
        logger.error(f"خطأ في معالجة النص: {e}")
        await msg.edit_text(f"❌ حدث خطأ: {str(e)}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل الصوتية"""
    await update.message.reply_text(
        "🎤 *الرسائل الصوتية*\n\n"
        "يمكنك استخدام ميزة النص الصوتي في تيليجرام ثم إرسال النص.\n"
        "أو قم بالتفعيل الكامل لهذه الميزة عبر ربط Whisper API في ملف `.env`",
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض آخر سجلات الصيانة"""
    chat_id = update.effective_chat.id
    args = context.args
    limit = 10

    if args and args[0].isdigit():
        limit = min(int(args[0]), 50)

    records = await db.get_recent_records(limit, chat_id)

    if not records:
        await update.message.reply_text("📭 لا توجد سجلات صيانة بعد.")
        return

    text = f"📋 *آخر {len(records)} سجلات صيانة:*\n\n"
    for r in records:
        text += (
            f"🔹 *#{r['id']}* | {r['work_date']} | {r['machine_name']}\n"
            f"   النوع: {r['maintenance_type']} | الوقت: {r['repair_hours'] or '?'} ساعة\n"
        )
        if r['work_details']:
            text += f"   _{r['work_details'][:80]}..._\n" if len(r['work_details']) > 80 else f"   _{r['work_details']}_\n"
        text += "\n"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة المخزون"""
    args = context.args

    # إضافة مخزون: /inventory add اسم_القطعة الكمية الوحدة
    if args and args[0].lower() == "add":
        if len(args) < 3:
            await update.message.reply_text(
                "❌ صيغة خاطئة.\nاستخدم: `/inventory add اسم_القطعة الكمية الوحدة`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        part_name = args[1]
        try:
            quantity = float(args[2])
            unit = args[3] if len(args) > 3 else "قطعة"
            await db.add_inventory_stock(part_name, quantity, unit)
            await update.message.reply_text(
                f"✅ تمت إضافة *{quantity} {unit}* من *{part_name}* للمخزون",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await update.message.reply_text("❌ الكمية يجب أن تكون رقماً")
        return

    # عرض المخزون
    inventory = await db.get_inventory_list()

    if not inventory:
        await update.message.reply_text(
            "📦 المخزون فارغ.\n"
            "استخدم `/inventory add اسم_القطعة الكمية` لإضافة قطع.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    text = "📦 *حالة المخزون الحالية:*\n\n"
    for item in inventory:
        stock = float(item['current_stock'])
        threshold = float(item['minimum_threshold'])
        status = "🔴 منخفض" if stock <= threshold else ("🟡 متوسط" if stock <= threshold * 2 else "🟢 كافٍ")
        text += f"{status} *{item['part_name']}*\n   الكمية: {stock} {item['unit']} (الحد الأدنى: {threshold})\n\n"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_insights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحليل ذكي لماكينة محددة"""
    args = context.args

    if not args:
        machines = await db.get_all_machines()
        if not machines:
            await update.message.reply_text("📊 لا توجد بيانات كافية للتحليل.")
            return

        text = "🤖 *الماكينات المتاحة للتحليل:*\n\n"
        for m in machines:
            text += f"• *{m['machine_name']}* - {m['total_records']} سجل\n"
        text += "\nاستخدم: `/insights اسم_الماكينة [عدد الأيام]`"
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    machine_name = " ".join(args[:-1]) if args[-1].isdigit() else " ".join(args)
    days = int(args[-1]) if args[-1].isdigit() else 90

    msg = await update.message.reply_text(f"🔍 جاري تحليل ماكينة *{machine_name}*...", parse_mode=ParseMode.MARKDOWN)

    history = await db.get_machine_maintenance_history(machine_name, days)
    analysis = await ai.analyze_machine_insights(machine_name, history, days)

    await msg.edit_text(
        f"📊 *تحليل: {machine_name}* (آخر {days} يوم)\n\n{analysis}",
        parse_mode=ParseMode.MARKDOWN
    )


# ──────────────────────────────────────────
# دوال مساعدة داخلية
# ──────────────────────────────────────────

def _format_confirmation(data: dict, record_id: int) -> str:
    """تنسيق رسالة التأكيد بعد الحفظ"""
    parts_text = ""
    parts = data.get("spare_parts", [])
    if parts:
        parts_text = "\n*قطع الغيار:*\n"
        for p in parts:
            parts_text += f"  • {p.get('name', '?')} × {p.get('quantity', 1)} {p.get('unit', 'قطعة')}\n"

    return (
        f"✅ *تم حفظ سجل الصيانة #{record_id}*\n\n"
        f"📅 التاريخ: {data.get('work_date', 'غير محدد')}\n"
        f"🔧 الماكينة: {data.get('machine_name', 'غير محدد')}\n"
        f"📌 نوع الصيانة: {data.get('maintenance_type', 'غير محدد')}\n"
        f"⏱ وقت الإصلاح: {data.get('repair_hours', '?')} ساعة\n"
        f"📝 التفاصيل: {(data.get('work_details') or '')[:150]}"
        f"{parts_text}"
    )


async def _check_and_notify_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحقق من المخزون وإرسال تنبيهات"""
    low_parts = await db.get_low_stock_parts()

    if low_parts:
        alert = "⚠️ *تنبيه المخزون* ⚠️\n\nالقطع التالية وصلت للحد الأدنى:\n\n"
        for part in low_parts:
            alert += f"🔴 *{part['part_name']}*: {float(part['current_stock'])} {part['unit']} (الحد: {float(part['minimum_threshold'])})\n"
        alert += "\n_يرجى إعادة الطلب في أقرب وقت_"

        await update.message.reply_text(alert, parse_mode=ParseMode.MARKDOWN)


async def _check_recurring_faults(update: Update, context: ContextTypes.DEFAULT_TYPE, machine_name: str):
    """التحقق من الأعطال المتكررة"""
    if not machine_name or machine_name == "غير محدد":
        return

    history = await db.get_machine_maintenance_history(machine_name, 30)
    alert = await ai.detect_recurring_faults(history, machine_name)

    if alert:
        await update.message.reply_text(alert, parse_mode=ParseMode.MARKDOWN)
