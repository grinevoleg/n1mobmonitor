import secrets
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models import APIKey


def generate_api_key() -> str:
    """Генерация безопасного API ключа"""
    return f"sk_live_{secrets.token_urlsafe(24)}"


def create_api_key(db: Session, description: Optional[str] = None) -> APIKey:
    """Создание нового API ключа"""
    key = generate_api_key()
    db_key = APIKey(
        key=key,
        description=description,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    return db_key


def revoke_api_key(db: Session, key: str) -> bool:
    """Отзыв API ключа"""
    db_key = db.query(APIKey).filter(APIKey.key == key).first()
    if db_key:
        db_key.is_active = False
        db.commit()
        return True
    return False


def validate_api_key(db: Session, key: str, rate_limit: int) -> Optional[APIKey]:
    """
    Валидация API ключа с проверкой rate limiting
    Возвращает APIKey если валиден, None если невалиден или превышен лимит
    """
    db_key = db.query(APIKey).filter(
        APIKey.key == key,
        APIKey.is_active == True
    ).first()
    
    if not db_key:
        return None
    
    now = datetime.utcnow()
    
    # Сброс счётчика если прошёл час
    if db_key.hourly_reset_at is None or now > db_key.hourly_reset_at:
        db_key.hourly_request_count = 0
        db_key.hourly_reset_at = now + timedelta(hours=1)
    
    # Проверка rate limit
    if db_key.hourly_request_count >= rate_limit:
        return None
    
    # Обновление счётчиков
    db_key.hourly_request_count += 1
    db_key.request_count += 1
    db_key.last_used_at = now
    
    db.commit()
    db.refresh(db_key)
    
    return db_key
