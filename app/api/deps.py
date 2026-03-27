from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from typing import Optional
import secrets

from app.database import get_db
from app.utils.security import validate_api_key
from app.config import settings
from app.models import Setting

# Заголовок для API ключа
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Basic Auth для администратора
admin_auth = HTTPBasic(auto_error=False)


async def get_api_key(
    request: Request,
    db: Session = Depends(get_db),
    api_key: Optional[str] = Depends(API_KEY_HEADER)
):
    """
    Зависимость для проверки API ключа

    Возвращает APIKey из БД если ключ валиден
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API ключ не предоставлен"
        )

    validated_key = validate_api_key(db, api_key, settings.rate_limit)

    if not validated_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный API ключ или превышен лимит запросов"
        )

    return validated_key


async def get_optional_api_key(
    request: Request,
    db: Session = Depends(get_db),
    api_key: Optional[str] = Depends(API_KEY_HEADER)
):
    """
    Зависимость для опциональной проверки API ключа

    Возвращает APIKey если ключ предоставлен и валиден, иначе None
    """
    if not api_key:
        return None

    return validate_api_key(db, api_key, settings.rate_limit)


async def get_admin_user(
    credentials: HTTPBasicCredentials = Depends(admin_auth),
    db: Session = Depends(get_db)
):
    """
    Зависимость для проверки администратора
    
    Проверяет логин/пароль из БД (настройки admin_username/admin_password)
    или из .env (ADMIN_USERNAME/ADMIN_PASSWORD)
    """
    # Получаем настройки из БД или используем значения из env
    db_setting = db.query(Setting).filter(Setting.key == "admin_username").first()
    admin_username = db_setting.value if db_setting else settings.__dict__.get("admin_username", "admin")
    
    db_setting = db.query(Setting).filter(Setting.key == "admin_password").first()
    admin_password = db_setting.value if db_setting else settings.__dict__.get("admin_password", "admin")
    
    # Проверка учётных данных
    if not credentials or not secrets.compare_digest(credentials.username, admin_username) or not secrets.compare_digest(credentials.password, admin_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return {"username": credentials.username}
