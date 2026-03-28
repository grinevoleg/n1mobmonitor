import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import Setting
from app.api.routes import router as api_router
from app.api.dashboard import router as dashboard_router
from app.api.alerts import router as alerts_router
from app.api.settings import router as settings_router
from app.api.telegram_users import router as telegram_users_router
from app.services.monitor import monitor_service
from app.services.telegram_bot import telegram_bot_service

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_default_settings():
    """Инициализация настроек по умолчанию"""
    db = SessionLocal()
    try:
        default_settings = {
            "monitor_interval": str(settings.monitor_interval),
            "monitor_jitter": str(settings.monitor_jitter),
            "email_enabled": "false",
            "telegram_enabled": "false",
            "smtp_host": "",
            "smtp_port": "587",
            "smtp_user": "",
            "smtp_password": "",
            "alert_email": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "admin_username": os.getenv("ADMIN_USERNAME", "admin"),
            "admin_password": os.getenv("ADMIN_PASSWORD", "admin"),
            "google_credentials": settings.google_credentials or "",
            "spreadsheet_id": settings.spreadsheet_id or "",
            "sheet_name": settings.sheet_name,
        }
        
        for key, value in default_settings.items():
            existing = db.query(Setting).filter(Setting.key == key).first()
            if not existing:
                db.add(Setting(key=key, value=value))
        
        db.commit()
        logger.info("Настройки по умолчанию инициализированы")
    except Exception as e:
        logger.error(f"Ошибка инициализации настроек: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("Запуск приложения...")

    # Создание таблиц БД
    Base.metadata.create_all(bind=engine)
    logger.info("База данных инициализирована")
    
    # Автоматическая миграция БД (исправление ENUM на TEXT)
    from migrate_db import migrate_database
    if migrate_database():
        logger.info("Миграция БД выполнена успешно")
    else:
        logger.warning("Миграция БД не выполнена, возможны ошибки")
    
    # Инициализация настроек по умолчанию
    init_default_settings()

    # Запуск фонового мониторинга
    monitor_service.start()
    
    # Запуск Telegram бота (только если включено в .env)
    import threading
    from app.config import settings
    
    if settings.telegram_bot_enabled and settings.telegram_bot_token:
        bot_thread = threading.Thread(
            target=telegram_bot_service.start,
            args=(settings.telegram_bot_token,),
            daemon=True
        )
        bot_thread.start()
        logger.info("Telegram bot thread started")
    else:
        logger.info("Telegram bot disabled (set TELEGRAM_BOT_ENABLED=true to enable)")

    yield

    # Shutdown
    logger.info("Остановка приложения...")
    monitor_service.stop()


# Создание приложения
app = FastAPI(
    title=settings.app_name,
    description="Сервис для безопасного мониторинга доступности приложений в App Store",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация роутеров
app.include_router(dashboard_router)
app.include_router(api_router)
app.include_router(alerts_router)
app.include_router(settings_router)
app.include_router(telegram_users_router)


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "service": settings.app_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
