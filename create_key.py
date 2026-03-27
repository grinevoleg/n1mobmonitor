#!/usr/bin/env python3
"""Скрипт для создания первого API ключа"""

from app.database import SessionLocal, Base, engine
from app.models import APIKey
from app.utils.security import generate_api_key

# Создаём таблицы если не существуют
Base.metadata.create_all(bind=engine)

# Создаём первый ключ
db = SessionLocal()
try:
    key = generate_api_key()
    db_key = APIKey(key=key, description="Default Key", is_active=True)
    db.add(db_key)
    db.commit()
    
    print("=" * 50)
    print("Первый API ключ создан!")
    print("=" * 50)
    print(f"Ключ: {key}")
    print("=" * 50)
    print("\nПример использования:")
    print(f'curl -X POST http://localhost:8000/api/v1/apps \\')
    print(f'  -H "X-API-Key: {key}" \\')
    print(f'  -H "Content-Type: application/json" \\')
    print(f'  -d \'{{"bundle_id": "com.example.app"}}\'')
    print()
finally:
    db.close()
