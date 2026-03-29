from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import TelegramUser, UserNotificationSettings
from app.schemas import TelegramUserResponse, TelegramUserUpdate, UserNotificationSettingsResponse, UserNotificationSettingsUpdate
from app.api.deps import get_api_key, get_admin_user

router = APIRouter(prefix="/api/v1/telegram-users", tags=["Telegram Users"])


def check_admin(db: Session, api_key_user):
    """Проверка что пользователь admin"""
    # Для простоты проверяем только API key
    # В реальной реализации нужно связать API key с Telegram user
    pass


@router.get("", response_model=List[TelegramUserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Получить список всех пользователей Telegram (admin only)"""
    users = db.query(TelegramUser).order_by(TelegramUser.created_at.desc()).offset(skip).limit(limit).all()
    return users


@router.get("/me", response_model=TelegramUserResponse)
def get_my_profile(
    telegram_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Получить мой профиль"""
    user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@router.put("/{user_id}/role", response_model=TelegramUserResponse)
def update_user_role(
    user_id: int,
    update_data: TelegramUserUpdate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_admin_user)
):
    """Изменить роль пользователя (admin only)"""
    user = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if update_data.role:
        if update_data.role not in ["admin", "developer", "manager"]:
            raise HTTPException(status_code=400, detail="Неверная роль")
        user.role = update_data.role
    
    user.updated_at = db.func.now()
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/{user_id}/approve", response_model=TelegramUserResponse)
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(get_admin_user)
):
    """Одобрить пользователя (admin only)"""
    user = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.status = "approved"
    user.updated_at = db.func.now()
    db.commit()
    db.refresh(user)

    return user


@router.post("/{user_id}/reject", response_model=TelegramUserResponse)
def reject_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(get_admin_user)
):
    """Отклонить пользователя (admin only)"""
    user = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.status = "rejected"
    user.updated_at = db.func.now()
    db.commit()
    db.refresh(user)

    return user


@router.get("/{user_id}/settings", response_model=UserNotificationSettingsResponse)
def get_notification_settings(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Получить настройки уведомлений пользователя"""
    user = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if not user.notification_settings:
        # Создаём настройки по умолчанию
        settings = UserNotificationSettings(telegram_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    else:
        settings = user.notification_settings
    
    return settings


@router.put("/{user_id}/settings", response_model=UserNotificationSettingsResponse)
def update_notification_settings(
    user_id: int,
    settings_data: UserNotificationSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Обновить настройки уведомлений пользователя"""
    user = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if not user.notification_settings:
        settings = UserNotificationSettings(telegram_id=user.id)
        db.add(settings)
    else:
        settings = user.notification_settings
    
    if settings_data.notify_status_change is not None:
        settings.notify_status_change = settings_data.notify_status_change
    if settings_data.notify_version_change is not None:
        settings.notify_version_change = settings_data.notify_version_change
    if settings_data.notify_error is not None:
        settings.notify_error = settings_data.notify_error
    if settings_data.notify_app_added is not None:
        settings.notify_app_added = settings_data.notify_app_added
    if settings_data.notify_unavailable is not None:
        settings.notify_unavailable = settings_data.notify_unavailable
    
    settings.updated_at = db.func.now()
    db.commit()
    db.refresh(settings)
    
    return settings
