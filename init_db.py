#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных
Создаёт все таблицы и настройки по умолчанию
"""

import sys
from sqlalchemy import inspect, text
from app.database import engine, Base, SessionLocal, init_db
from app.models import Setting

def check_tables_exist():
    """Проверка существования таблиц"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    required_tables = ['apps', 'check_history', 'api_keys', 'settings', 'alerts']
    
    print("📊 Проверка таблиц...")
    print(f"Найдено таблиц: {len(tables)}")
    
    missing = []
    for table in required_tables:
        if table in tables:
            print(f"  ✅ {table}")
        else:
            print(f"  ❌ {table} (отсутствует)")
            missing.append(table)
    
    return len(missing) == 0


def init_settings():
    """Инициализация настроек по умолчанию"""
    db = SessionLocal()
    try:
        default_settings = {
            "monitor_interval": "30",
            "monitor_jitter": "5",
            "email_enabled": "false",
            "telegram_enabled": "false",
            "smtp_host": "",
            "smtp_port": "587",
            "smtp_user": "",
            "smtp_password": "",
            "alert_email": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "admin_username": "admin",
            "admin_password": "admin",
        }
        
        created_count = 0
        for key, value in default_settings.items():
            existing = db.query(Setting).filter(Setting.key == key).first()
            if not existing:
                db.add(Setting(key=key, value=value))
                created_count += 1
        
        db.commit()
        print(f"✅ Создано настроек: {created_count}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
        return False
    finally:
        db.close()
    
    return True


def main():
    """Основная функция"""
    print("🚀 Инициализация базы данных...\n")
    
    # Проверка подключения к БД
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("✅ Подключение к базе данных успешно\n")
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        print("\nПроверьте DATABASE_URL в .env файле")
        sys.exit(1)
    
    # Проверка таблиц
    if not check_tables_exist():
        print("\n📝 Создание таблиц...")
        init_db()
        print("✅ Таблицы созданы\n")
    else:
        print("\n✅ Все таблицы существуют\n")
    
    # Инициализация настроек
    print("⚙️  Инициализация настроек...")
    if init_settings():
        print("✅ Настройки инициализированы\n")
    
    print("✨ Инициализация завершена успешно!")
    print("\n📝 Данные для входа:")
    print("   Логин: admin")
    print("   Пароль: admin")
    print("\n⚠️  Не забудьте сменить пароль в настройках!")


if __name__ == "__main__":
    main()
