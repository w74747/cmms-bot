"""
database.py - إدارة قاعدة البيانات PostgreSQL
"""
import os
import logging
from datetime import datetime
import asyncpg

logger = logging.getLogger(__name__)

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=os.environ["DATABASE_URL"],
            min_size=2,
            max_size=10
        )
    return _pool


async def init_db():
    """إنشاء الجداول عند بدء التشغيل"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_records (
                id SERIAL PRIMARY KEY,
                work_date DATE NOT NULL,
                machine_name VARCHAR(200) NOT NULL,
                maintenance_type VARCHAR(50) NOT NULL,
                work_details TEXT,
                repair_hours NUMERIC(6,2),
                technician VARCHAR(200),
                image_file_id VARCHAR(500),
                raw_extracted_json JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                chat_id BIGINT
            );

            CREATE TABLE IF NOT EXISTS spare_parts_used (
                id SERIAL PRIMARY KEY,
                record_id INTEGER REFERENCES maintenance_records(id) ON DELETE CASCADE,
                part_name VARCHAR(300) NOT NULL,
                quantity NUMERIC(10,3) NOT NULL,
                unit VARCHAR(50) DEFAULT 'قطعة'
            );

            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                part_name VARCHAR(300) NOT NULL UNIQUE,
                current_stock NUMERIC(10,3) DEFAULT 0,
                minimum_threshold NUMERIC(10,3) DEFAULT 5,
                unit VARCHAR(50) DEFAULT 'قطعة',
                last_updated TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id SERIAL PRIMARY KEY,
                part_name VARCHAR(300) NOT NULL,
                transaction_type VARCHAR(20) NOT NULL,
                quantity NUMERIC(10,3) NOT NULL,
                record_id INTEGER REFERENCES maintenance_records(id),
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_maintenance_machine ON maintenance_records(machine_name);
            CREATE INDEX IF NOT EXISTS idx_maintenance_date ON maintenance_records(work_date);
            CREATE INDEX IF NOT EXISTS idx_inventory_part ON inventory(part_name);
        """)
    logger.info("✅ الجداول جاهزة")


async def save_maintenance_record(data: dict, chat_id: int, image_file_id: str = None) -> int:
    """حفظ سجل صيانة جديد"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # حفظ السجل الرئيسي
            record_id = await conn.fetchval("""
                INSERT INTO maintenance_records
                    (work_date, machine_name, maintenance_type, work_details,
                     repair_hours, technician, image_file_id, raw_extracted_json, chat_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """,
                data.get("work_date") or datetime.today().date(),
                data.get("machine_name", "غير محدد"),
                data.get("maintenance_type", "غير محدد"),
                data.get("work_details", ""),
                data.get("repair_hours"),
                data.get("technician"),
                image_file_id,
                data,
                chat_id
            )

            # حفظ قطع الغيار
            parts = data.get("spare_parts", [])
            for part in parts:
                part_name = part.get("name") or part.get("part_name", "")
                quantity = float(part.get("quantity", 1))
                unit = part.get("unit", "قطعة")
                if part_name:
                    await conn.execute("""
                        INSERT INTO spare_parts_used (record_id, part_name, quantity, unit)
                        VALUES ($1, $2, $3, $4)
                    """, record_id, part_name, quantity, unit)

                    # تحديث المخزون
                    await _update_inventory(conn, part_name, quantity, unit, record_id)

            return record_id


async def _update_inventory(conn, part_name: str, used_qty: float, unit: str, record_id: int):
    """تحديث المخزون عند استخدام قطعة غيار"""
    # إنشاء السجل إن لم يوجد
    await conn.execute("""
        INSERT INTO inventory (part_name, current_stock, unit)
        VALUES ($1, 0, $2)
        ON CONFLICT (part_name) DO NOTHING
    """, part_name, unit)

    # خصم الكمية
    await conn.execute("""
        UPDATE inventory
        SET current_stock = GREATEST(0, current_stock - $1),
            last_updated = NOW()
        WHERE part_name = $2
    """, used_qty, part_name)

    # تسجيل الحركة
    await conn.execute("""
        INSERT INTO inventory_transactions (part_name, transaction_type, quantity, record_id)
        VALUES ($1, 'استخدام', $2, $3)
    """, part_name, used_qty, record_id)


async def get_low_stock_parts(threshold_multiplier: float = 1.0) -> list:
    """جلب القطع التي وصلت للحد الأدنى"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT part_name, current_stock, minimum_threshold, unit
            FROM inventory
            WHERE current_stock <= minimum_threshold * $1
            ORDER BY (current_stock / NULLIF(minimum_threshold, 0)) ASC
        """, threshold_multiplier)


async def get_inventory_list() -> list:
    """جلب قائمة المخزون كاملة"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT part_name, current_stock, minimum_threshold, unit, last_updated
            FROM inventory
            ORDER BY part_name
        """)


async def get_machine_maintenance_history(machine_name: str, days: int = 90) -> list:
    """جلب سجل صيانة ماكينة معينة"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT mr.*, 
                   json_agg(json_build_object(
                       'part_name', sp.part_name,
                       'quantity', sp.quantity,
                       'unit', sp.unit
                   )) FILTER (WHERE sp.id IS NOT NULL) as parts
            FROM maintenance_records mr
            LEFT JOIN spare_parts_used sp ON sp.record_id = mr.id
            WHERE LOWER(mr.machine_name) LIKE LOWER($1)
              AND mr.work_date >= NOW() - INTERVAL '1 day' * $2
            GROUP BY mr.id
            ORDER BY mr.work_date DESC
        """, f"%{machine_name}%", days)


async def get_all_machines() -> list:
    """جلب أسماء جميع الماكينات"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT DISTINCT machine_name, COUNT(*) as total_records,
                   MAX(work_date) as last_maintenance
            FROM maintenance_records
            GROUP BY machine_name
            ORDER BY machine_name
        """)


async def get_recent_records(limit: int = 10, chat_id: int = None) -> list:
    """جلب آخر سجلات الصيانة"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if chat_id:
            return await conn.fetch("""
                SELECT * FROM maintenance_records
                WHERE chat_id = $1
                ORDER BY created_at DESC LIMIT $2
            """, chat_id, limit)
        return await conn.fetch("""
            SELECT * FROM maintenance_records
            ORDER BY created_at DESC LIMIT $1
        """, limit)


async def add_inventory_stock(part_name: str, quantity: float, unit: str = "قطعة", notes: str = ""):
    """إضافة مخزون لقطعة غيار"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                INSERT INTO inventory (part_name, current_stock, unit)
                VALUES ($1, $2, $3)
                ON CONFLICT (part_name) DO UPDATE
                SET current_stock = inventory.current_stock + $2,
                    last_updated = NOW()
            """, part_name, quantity, unit)

            await conn.execute("""
                INSERT INTO inventory_transactions (part_name, transaction_type, quantity, notes)
                VALUES ($1, 'إضافة', $2, $3)
            """, part_name, quantity, notes)


async def set_minimum_threshold(part_name: str, threshold: float):
    """تحديث الحد الأدنى لقطعة"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE inventory SET minimum_threshold = $1
            WHERE part_name = $2
        """, threshold, part_name)
