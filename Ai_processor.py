"""
ai_processor.py - معالجة الذكاء الاصطناعي باستخدام Anthropic API
Vision OCR + تحليل البيانات + الرؤى الاستباقية
"""
import os
import base64
import json
import logging
from datetime import datetime
import anthropic

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

EXTRACTION_PROMPT = """أنت نظام متخصص في استخراج بيانات تقارير الصيانة الصناعية.

حلل الصورة المرفقة (قد تكون ورقة صيانة مكتوبة بخط اليد أو مطبوعة) واستخرج البيانات التالية بدقة:

أعد **فقط** كائن JSON صالح بهذا الشكل بدون أي نص إضافي:
{
  "work_date": "YYYY-MM-DD أو null إن لم يوجد",
  "machine_name": "اسم أو رقم الماكينة",
  "maintenance_type": "وقائية أو علاجية أو طارئة",
  "work_details": "وصف تفصيلي للعمل المنفذ",
  "spare_parts": [
    {"name": "اسم القطعة", "quantity": 1, "unit": "قطعة/لتر/متر/كغ"}
  ],
  "repair_hours": 0.0,
  "technician": "اسم الفني إن وُجد أو null",
  "notes": "ملاحظات إضافية إن وجدت"
}

قواعد مهمة:
- إذا كان التاريخ غير واضح، اكتب null
- نوع الصيانة: إذا كانت للوقاية = "وقائية"، لإصلاح عطل = "علاجية"، لعطل مفاجئ = "طارئة"
- قطع الغيار: اذكر كل قطعة بشكل منفصل مع الكمية
- ساعات الإصلاح: رقم عشري (مثال: 1.5 لساعة ونصف)
- إذا لم تجد معلومة، ضع null أو [] للمصفوفات
"""

TEXT_EXTRACTION_PROMPT = """أنت نظام متخصص في استخراج بيانات تقارير الصيانة الصناعية من النصوص.

المستخدم أرسل نصاً يصف عملية صيانة. استخرج البيانات وأعد **فقط** كائن JSON صالح:
{
  "work_date": "YYYY-MM-DD أو null",
  "machine_name": "اسم أو رقم الماكينة",
  "maintenance_type": "وقائية أو علاجية أو طارئة",
  "work_details": "وصف تفصيلي",
  "spare_parts": [
    {"name": "اسم القطعة", "quantity": 1, "unit": "قطعة"}
  ],
  "repair_hours": 0.0,
  "technician": null,
  "notes": null
}

إذا كان النص لا يصف صيانة، أعد: {"error": "النص لا يحتوي على بيانات صيانة"}
"""

INSIGHTS_PROMPT = """أنت مهندس صيانة خبير. حلل سجل الصيانة التالي لماكينة {machine_name} خلال آخر {days} يوماً:

{history_json}

قدم تحليلاً شاملاً يتضمن:
1. **نمط الأعطال**: هل هناك عطل يتكرر؟ كم مرة؟
2. **تشخيص محتمل**: ما السبب الجذري المحتمل للتكرار؟
3. **قطع الغيار الأكثر استهلاكاً**
4. **التوصية**: إجراء وقائي أو إصلاح جذري مقترح
5. **درجة الخطورة**: منخفضة / متوسطة / عالية / حرجة

أجب بالعربية بشكل موجز ومهني.
"""


async def extract_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """استخراج بيانات الصيانة من صورة باستخدام Claude Vision"""
    try:
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": EXTRACTION_PROMPT
                    }
                ]
            }]
        )

        response_text = message.content[0].text.strip()
        # تنظيف الاستجابة من الأكواد الزائدة
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        data = json.loads(response_text)
        logger.info(f"✅ استخرجت بيانات الصورة: {data.get('machine_name', 'غير محدد')}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"خطأ في تحليل JSON: {e}")
        return {"error": f"فشل تحليل البيانات: {str(e)}"}
    except Exception as e:
        logger.error(f"خطأ في معالجة الصورة: {e}")
        return {"error": str(e)}


async def extract_from_text(text: str) -> dict:
    """استخراج بيانات الصيانة من نص"""
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": f"{TEXT_EXTRACTION_PROMPT}\n\nالنص:\n{text}"
            }]
        )

        response_text = message.content[0].text.strip()
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        data = json.loads(response_text)
        return data

    except json.JSONDecodeError:
        return {"error": "لم أتمكن من استخراج بيانات صيانة من النص"}
    except Exception as e:
        logger.error(f"خطأ في معالجة النص: {e}")
        return {"error": str(e)}


async def transcribe_voice(audio_bytes: bytes) -> str:
    """تحويل الصوت إلى نص (يستخدم Whisper عبر API خارجي أو معالجة محلية)"""
    # ملاحظة: Anthropic لا يدعم الصوت مباشرة
    # يمكن استخدام OpenAI Whisper أو Google Speech-to-Text
    # هنا نرجع رسالة توضيحية
    return None


async def analyze_machine_insights(machine_name: str, history: list, days: int = 90) -> str:
    """تحليل سجل الصيانة وإنتاج رؤى استباقية"""
    if not history:
        return f"لا يوجد سجل صيانة لـ {machine_name} خلال آخر {days} يوم."

    # تجهيز البيانات للتحليل
    history_simplified = []
    fault_counter = {}

    for record in history:
        entry = {
            "date": str(record["work_date"]),
            "type": record["maintenance_type"],
            "details": record["work_details"][:200] if record["work_details"] else "",
            "hours": float(record["repair_hours"] or 0)
        }
        history_simplified.append(entry)

        # عد تكرار الأعطال
        details_lower = (record["work_details"] or "").lower()
        for keyword in ["محرك", "بمب", "حزام", "بيرينج", "تسريب", "شورت", "حرارة", "ضغط", "صمام"]:
            if keyword in details_lower:
                fault_counter[keyword] = fault_counter.get(keyword, 0) + 1

    history_json = json.dumps(history_simplified, ensure_ascii=False, indent=2)

    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": INSIGHTS_PROMPT.format(
                    machine_name=machine_name,
                    days=days,
                    history_json=history_json
                )
            }]
        )

        analysis = message.content[0].text.strip()

        # التحقق من تكرار الأعطال وإضافة تنبيه إضافي
        repeated_faults = [k for k, v in fault_counter.items() if v >= 3]
        if repeated_faults:
            fault_str = "، ".join(repeated_faults)
            analysis = f"⚠️ **تنبيه**: الماكينة {machine_name} تعاني من تكرار عطل في: {fault_str}. قد يكون هناك مشكلة جذرية!\n\n{analysis}"

        return analysis

    except Exception as e:
        logger.error(f"خطأ في تحليل الرؤى: {e}")
        return f"تعذر إجراء التحليل: {str(e)}"


async def detect_recurring_faults(history: list, machine_name: str) -> str | None:
    """
    الكشف عن الأعطال المتكررة وإرجاع تنبيه إن وُجدت
    يُستخدم بعد كل تسجيل جديد
    """
    if len(history) < 3:
        return None

    recent = history[:5]  # آخر 5 سجلات

    # تجميع الكلمات المفتاحية للأعطال
    fault_words = {}
    for record in recent:
        details = (record["work_details"] or "").lower()
        maintenance_type = record.get("maintenance_type", "")

        if maintenance_type == "علاجية":
            words = details.split()
            for word in words:
                if len(word) > 3:
                    fault_words[word] = fault_words.get(word, 0) + 1

    # الأعطال التي تكررت 3 مرات أو أكثر
    repeated = {k: v for k, v in fault_words.items() if v >= 3}

    if repeated:
        top_fault = max(repeated, key=repeated.get)
        return (
            f"🚨 *تنبيه تلقائي*\n"
            f"الماكينة *{machine_name}* تعاني من تكرار عطل يتعلق بـ: *{top_fault}* "
            f"({repeated[top_fault]} مرات في آخر 5 سجلات)\n"
            f"_يُنصح بإجراء فحص شامل للكشف عن المشكلة الجذرية_"
        )

    return None
