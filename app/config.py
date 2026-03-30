import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # App version
    app_version: str = "1.0.0"
    
    # Database
    database_url: str = "sqlite:///./app_store_monitor.db"
    
    # Google Sheets
    google_credentials: Optional[str] = None
    spreadsheet_id: Optional[str] = None
    sheet_name: str = "AppStoreMonitor"
    
    # Monitoring interval (minutes)
    monitor_interval: int = 30  # Увеличено с 10 до 30 для безопасности
    
    # Monitoring jitter (minutes) - случайное отклонение от интервала
    monitor_jitter: int = 5  # ±5 минут
    
    # Admin credentials
    admin_username: str = "admin"
    admin_password: str = "changeme"
    
    # Telegram bot token
    telegram_bot_token: Optional[str] = None
    
    # Enable Telegram bot (for production only)
    telegram_bot_enabled: bool = False
    
    # App name
    app_name: str = "App Store Monitor"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = 'ignore'  # Игнорировать лишние поля


# Чтение версии из файла VERSION
try:
    with open('VERSION', 'r') as f:
        version_from_file = f.read().strip()
except:
    version_from_file = "1.0.0"

settings = Settings()
if settings.app_version == "1.0.0":  # default value
    settings.app_version = version_from_file
