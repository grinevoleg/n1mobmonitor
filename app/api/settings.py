from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict
import logging

from app.database import get_db
from app.models import App, Setting
from app.schemas import SettingsUpdate, AppUpdate
from app.api.deps import get_admin_user
from app.services.notifier import test_email_notification, test_telegram_notification, get_all_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


@router.get("", response_model=Dict[str, str])
def get_settings(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Получить все настройки"""
    return get_all_settings(db)


@router.put("", response_model=Dict[str, str])
def update_settings(
    settings_data: SettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Обновить настройки (логин/пароль админа только через .env, не через API)"""
    result = {}
    for key, value in settings_data.settings.items():
        if key in ("admin_username", "admin_password"):
            continue
        setting = update_setting(db, key, str(value))
        result[key] = setting.value
    return result


def update_setting(db: Session, key: str, value: str) -> Setting:
    """Обновление или создание настройки"""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


@router.post("/test-email")
def test_email(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Тест Email уведомления"""
    import asyncio
    result = asyncio.run(test_email_notification())
    if result:
        return {"status": "ok", "message": "Email отправлен успешно"}
    else:
        raise HTTPException(status_code=500, detail="Не удалось отправить Email. Проверьте настройки SMTP.")


@router.post("/test-telegram")
def test_telegram(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Тест Telegram уведомления"""
    import asyncio
    result = asyncio.run(test_telegram_notification())
    if result:
        return {"status": "ok", "message": "Telegram сообщение отправлено успешно"}
    else:
        raise HTTPException(status_code=500, detail="Не удалось отправить Telegram сообщение. Проверьте настройки.")


# === Управление приложениями ===

@router.get("/apps")
def get_settings_apps(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Получить список приложений для страницы настроек"""
    apps = db.query(App).order_by(App.created_at.desc()).all()
    return apps


@router.post("/apps", status_code=201)
async def add_app(
    app_data: AppUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Добавить приложение для мониторинга с немедленной проверкой"""
    if not app_data.bundle_id and not app_data.app_id:
        raise HTTPException(status_code=400, detail="Необходимо указать bundle_id или app_id")

    # Проверка на дубликат
    if app_data.bundle_id:
        existing = db.query(App).filter(App.bundle_id == app_data.bundle_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Приложение с таким Bundle ID уже существует")

    if app_data.app_id:
        existing = db.query(App).filter(App.app_id == str(app_data.app_id)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Приложение с таким Apple ID уже существует")

    db_app = App(
        bundle_id=app_data.bundle_id,
        app_id=str(app_data.app_id) if app_data.app_id else None,
        is_active=True
    )
    db.add(db_app)
    db.commit()
    app_id = db_app.id
    db.refresh(db_app)
    
    # Немедленная проверка приложения с флагом нового приложения
    from app.services.monitor import monitor_service
    try:
        result = await monitor_service.check_single_app(app_id, is_new_app=True)
        logger.info(f"Новое приложение проверено: {result}")
    except Exception as e:
        logger.warning(f"Ошибка при проверке нового приложения: {e}")
    
    # Обновляем данные из БД
    db_app = db.query(App).filter(App.id == app_id).first()

    return db_app


@router.put("/apps/{app_id}")
def update_app(
    app_id: int,
    app_data: AppUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Редактировать приложение"""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Приложение не найдено")

    # Проверка на дубликат при изменении bundle_id
    if app_data.bundle_id and app_data.bundle_id != app.bundle_id:
        existing = db.query(App).filter(
            App.bundle_id == app_data.bundle_id,
            App.id != app_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Приложение с таким Bundle ID уже существует")

    # Проверка на дубликат при изменении app_id
    if app_data.app_id and str(app_data.app_id) != app.app_id:
        existing = db.query(App).filter(
            App.app_id == str(app_data.app_id),
            App.id != app_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Приложение с таким Apple ID уже существует")

    if app_data.bundle_id is not None:
        app.bundle_id = app_data.bundle_id
    if app_data.app_id is not None:
        app.app_id = str(app_data.app_id)
    if app_data.is_active is not None:
        app.is_active = app_data.is_active

    db.commit()
    db.refresh(app)

    return app


@router.delete("/apps/{app_id}", status_code=204)
def delete_app(
    app_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Удалить приложение из мониторинга"""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Приложение не найдено")

    db.delete(app)
    db.commit()
    return None
