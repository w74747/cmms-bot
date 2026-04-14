import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    # إنشاء جدول الصيانة إذا لم يكن موجوداً
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS maintenance_records (
            id SERIAL PRIMARY KEY,
            work_date TEXT,
            machine_name TEXT,
            maintenance_type TEXT,
            work_details TEXT,
            technician TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    await conn.close()
    print("✅ تم تجهيز قاعدة البيانات بنجاح")
