from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
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
    """Схема записи истории проверок"""
    id: int
    app_id: int
    status: str
    version: Optional[str] = None
    message: Optional[str] = None
    checked_at: datetime
    
    class Config:
        from_attributes = True


# === API Key Schemas ===

class APIKeyCreate(BaseModel):
    """Схема для создания API ключа"""
    description: Optional[str] = Field(None, max_length=256)


class APIKeyResponse(BaseModel):
    """Схема ответа с API ключом"""
    id: int
    key: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    
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
