from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Dict, Any
import re


# === App Schemas ===

class AppCreate(BaseModel):
    """Схема для добавления приложения"""
    bundle_id: Optional[str] = Field(None, min_length=3, max_length=256)
    app_id: Optional[int] = Field(None, gt=0)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.bundle_id and not self.app_id:
            raise ValueError('Необходимо указать bundle_id или app_id')

    @validator('bundle_id')
    def validate_bundle_id(cls, v):
        if v is not None and not re.match(r'^[a-zA-Z0-9.-]+$', v):
            raise ValueError('Bundle ID должен содержать только латинские буквы, цифры, точки и дефисы')
        return v


class AppResponse(BaseModel):
    """Схема ответа с информацией о приложении"""
    id: int
    bundle_id: Optional[str] = None
    app_id: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None
    icon_url: Optional[str] = None  # App icon URL
    description: Optional[str] = None  # App description
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_check_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None

    class Config:
        from_attributes = True


class AppStatusResponse(BaseModel):
    """Схема статуса приложения для дашборда"""
    id: int
    bundle_id: str
    name: Optional[str] = None
    version: Optional[str] = None
    last_check_at: Optional[datetime] = None
    last_status: Optional[str] = None
    status_display: str  # "available", "unavailable", "error"
    uptime_percent: float = 0.0


# === Check History Schemas ===

class CheckHistoryResponse(BaseModel):
    """Схема записи истории проверок (audit — распарсенный audit_json для разбора)"""
    id: int
    app_id: int
    status: str
    version: Optional[str] = None
    message: Optional[str] = None
    checked_at: datetime
    audit: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# === Dashboard Schemas ===

class DashboardAppStatus(BaseModel):
    """Статус приложения для дашборда"""
    id: int
    bundle_id: str
    name: Optional[str] = None
    version: Optional[str] = None
    last_status: Optional[str] = None
    last_check_at: Optional[datetime] = None
    status_icon: str  # 🟢, 🔴, 🟡


class DashboardResponse(BaseModel):
    """Ответ для дашборда"""
    apps: List[DashboardAppStatus]
    total: int
    available: int
    unavailable: int
    error: int
    last_updated: datetime


# === Alert Schemas ===

class AlertResponse(BaseModel):
    """Схема ответа с алертом"""
    id: int
    app_id: int
    app_name: Optional[str] = None
    app_identifier: Optional[str] = None
    alert_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    message: str
    is_read: bool
    created_at: datetime
    alert_emoji: str

    class Config:
        from_attributes = True


class AlertStats(BaseModel):
    """Статистика алертов"""
    total: int
    unread: int
    by_type: dict
    by_type_unread: dict


# === Setting Schemas ===

class SettingResponse(BaseModel):
    """Схема ответа с настройкой"""
    key: str
    value: str
    updated_at: datetime

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    """Схема для обновления настроек"""
    settings: dict


class TestNotificationRequest(BaseModel):
    """Запрос на тест уведомления"""
    pass


# === App Update Schema ===

class AppUpdate(BaseModel):
    """Схема для редактирования приложения"""
    bundle_id: Optional[str] = None
    app_id: Optional[int] = None
    is_active: Optional[bool] = None


# === Telegram User Schemas ===

class TelegramUserResponse(BaseModel):
    """Схема ответа с пользователем Telegram"""
    id: int
    telegram_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    approved_by: Optional[int] = None

    class Config:
        from_attributes = True


class TelegramUserUpdate(BaseModel):
    """Схема для обновления пользователя"""
    role: Optional[str] = None
    status: Optional[str] = None


class UserNotificationSettingsResponse(BaseModel):
    """Схема настроек уведомлений"""
    id: int
    telegram_id: int
    notify_status_change: bool
    notify_version_change: bool
    notify_error: bool
    notify_app_added: bool
    notify_unavailable: bool

    class Config:
        from_attributes = True


class UserNotificationSettingsUpdate(BaseModel):
    """Схема для обновления настроек уведомлений"""
    notify_status_change: Optional[bool] = None
    notify_version_change: Optional[bool] = None
    notify_error: Optional[bool] = None
    notify_app_added: Optional[bool] = None
    notify_unavailable: Optional[bool] = None
