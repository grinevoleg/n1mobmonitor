"""
Скрипт миграции базы данных
Исправляет тип колонок role и status с ENUM на TEXT
"""

import logging
from sqlalchemy import text, inspect
from app.database import engine, SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_database():
    """Выполнить миграцию базы данных"""
    logger.info("Starting database migration...")
    
    db = SessionLocal()
    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        # Удаление устаревшей таблицы API-ключей
        if "api_keys" in table_names:
            logger.info("Dropping legacy api_keys table...")
            db.execute(text("DROP TABLE IF EXISTS api_keys"))
            db.commit()
            logger.info("✅ api_keys table removed")

        # Миграция для apps (icon_url, description)
        if "apps" in table_names:
            apps_columns = {col['name']: col for col in inspector.get_columns("apps")}
            
            if "icon_url" not in apps_columns:
                logger.info("Adding icon_url column to apps table...")
                db.execute(text("ALTER TABLE apps ADD COLUMN icon_url TEXT"))
                db.commit()
                logger.info("✅ icon_url column added")
            
            if "description" not in apps_columns:
                logger.info("Adding description column to apps table...")
                db.execute(text("ALTER TABLE apps ADD COLUMN description TEXT"))
                db.commit()
                logger.info("✅ description column added")
        
        # Миграция для telegram_users
        if "telegram_users" not in inspector.get_table_names():
            logger.info("Table telegram_users does not exist yet")
            return True
        
        columns = {col['name']: col for col in inspector.get_columns("telegram_users")}
        
        if "role" not in columns:
            logger.error("Column 'role' not found in telegram_users table")
            return False
        
        # Проверка является ли тип ENUM
        role_type = str(columns["role"]["type"])
        logger.info(f"Current role column type: {role_type}")
        
        if "USERROLE" in role_type.upper() or "ENUM" in role_type.upper():
            logger.warning("ENUM type detected, performing migration...")
            
            # Выполнение миграции
            migration_sql = """
            -- Изменить тип колонки role с ENUM на TEXT
            ALTER TABLE telegram_users 
                ALTER COLUMN role TYPE TEXT 
                USING role::text;
            
            -- Изменить тип колонки status с ENUM на TEXT  
            ALTER TABLE telegram_users 
                ALTER COLUMN status TYPE TEXT 
                USING status::text;
            
            -- Удалить ENUM типы если существуют
            DROP TYPE IF EXISTS userrole CASCADE;
            DROP TYPE IF EXISTS userstatus CASCADE;
            """
            
            db.execute(text(migration_sql))
            db.commit()
            
            logger.info("✅ Database migration completed successfully!")
            logger.info("   - Changed role column to TEXT")
            logger.info("   - Changed status column to TEXT")
            logger.info("   - Dropped userrole ENUM type")
            logger.info("   - Dropped userstatus ENUM type")
            
            return True
        else:
            logger.info("✅ Database is already up to date (using TEXT types)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = migrate_database()
    exit(0 if success else 1)
