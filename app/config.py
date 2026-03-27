import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Database
    database_url: str = "sqlite:///./app_store_monitor.db"
    
    # Google Sheets
    google_credentials: Optional[str] = None
    spreadsheet_id: Optional[str] = None
    sheet_name: str = "AppStoreMonitor"
    
    # Rate limiting
    rate_limit: int = 100
    
    # Monitoring interval (minutes)
    monitor_interval: int = 30  # Увеличено с 10 до 30 для безопасности
    
    # Monitoring jitter (minutes) - случайное отклонение от интервала
    monitor_jitter: int = 5  # ±5 минут
    
    # Admin credentials
    admin_username: str = "admin"
    admin_password: str = "changeme"
    
    # App name
    app_name: str = "App Store Monitor"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = 'ignore'  # Игнорировать лишние поля


settings = Settings()
