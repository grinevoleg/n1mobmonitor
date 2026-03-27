import json
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import Alert, App

logger = logging.getLogger(__name__)


def check_and_create_alerts(
    db: Session,
    app: App,
    result: Dict[str, Any],
    is_new_app: bool = False
) -> List[Alert]:
    """
    Проверка изменений и создание алертов
    
    Args:
        db: сессия БД
        app: модель приложения
        result: результат проверки из App Store API
        is_new_app: флаг нового приложения
        
    Returns:
        список созданных алертов
    """
    alerts = []
    
    old_status = app.last_status
    new_status = result.get("status")
    old_version = app.version
    new_version = result.get("version")
    old_name = app.name
    new_name = result.get("name")
    
    app_identifier = app.bundle_id or app.app_id or str(app.id)
    app_name = app.name or app_identifier
    
    # 0. Alert о добавлении нового приложения
    if is_new_app and new_status is not None:
        status_emoji = {"available": "🟢", "unavailable": "🔴", "error": "🟡"}.get(new_status, "⚪")
        alert = Alert(
            app_id=app.id,
            alert_type="app_added",
            old_value=None,
            new_value=json.dumps({"status": new_status, "name": new_name, "version": new_version}),
            message=f"Приложение добавлено в мониторинг. Статус: {status_emoji} {new_status}",
            created_at=datetime.utcnow()
        )
        db.add(alert)
        alerts.append(alert)
        logger.info(f"Создан алерт app_added для {app_name}")
    
    # 1. Alert на изменение статуса (не показываем для новых приложений)
    if old_status != new_status and new_status is not None and not is_new_app:
        alert = Alert(
            app_id=app.id,
            alert_type="status_change",
            old_value=json.dumps({"status": old_status}),
            new_value=json.dumps({"status": new_status}),
            message=f"Статус изменился: {old_status or 'N/A'} → {new_status}",
            created_at=datetime.utcnow()
        )
        db.add(alert)
        alerts.append(alert)
        logger.info(f"Создан алерт status_change для {app_name}: {old_status} → {new_status}")
    
    # 2. Alert на изменение версии
    if old_version != new_version and new_version is not None:
        alert = Alert(
            app_id=app.id,
            alert_type="version_change",
            old_value=json.dumps({"version": old_version}),
            new_value=json.dumps({"version": new_version}),
            message=f"Версия изменилась: {old_version or 'N/A'} → {new_version}",
            created_at=datetime.utcnow()
        )
        db.add(alert)
        alerts.append(alert)
        logger.info(f"Создан алерт version_change для {app_name}: {old_version} → {new_version}")
    
    # 3. Alert на изменение названия (редко, но бывает)
    if old_name != new_name and new_name is not None:
        alert = Alert(
            app_id=app.id,
            alert_type="name_change",
            old_value=json.dumps({"name": old_name}),
            new_value=json.dumps({"name": new_name}),
            message=f"Название изменилось: {old_name or 'N/A'} → {new_name}",
            created_at=datetime.utcnow()
        )
        db.add(alert)
        alerts.append(alert)
        logger.info(f"Создан алерт name_change для {app_name}: {old_name} → {new_name}")
    
    # 4. Alert на ошибку
    if new_status == "error":
        error_message = result.get("message", "Неизвестная ошибка")
        alert = Alert(
            app_id=app.id,
            alert_type="error",
            old_value=None,
            new_value=json.dumps({"error": error_message}),
            message=f"Ошибка проверки: {error_message}",
            created_at=datetime.utcnow()
        )
        db.add(alert)
        alerts.append(alert)
        logger.warning(f"Создан алерт error для {app_name}: {error_message}")
    
    # 5. Alert на недоступность приложения
    if new_status == "unavailable":
        alert = Alert(
            app_id=app.id,
            alert_type="unavailable",
            old_value=None,
            new_value=None,
            message=f"Приложение не найдено в App Store",
            created_at=datetime.utcnow()
        )
        db.add(alert)
        alerts.append(alert)
        logger.warning(f"Создан алерт unavailable для {app_name}")
    
    return alerts


def get_alert_emoji(alert_type: str) -> str:
    """Возвращает emoji для типа алерта"""
    emoji_map = {
        "status_change": "🔴",
        "version_change": "🔵",
        "name_change": "🟣",
        "error": "🟡",
        "unavailable": "🔴",
        "app_added": "🆕",
        "test": "⚪"
    }
    return emoji_map.get(alert_type, "⚪")


def get_alert_color(alert_type: str) -> str:
    """Возвращает цвет для типа алерта (для UI)"""
    color_map = {
        "status_change": "#ff4757",  # красный
        "version_change": "#00d9ff",  # голубой
        "name_change": "#a55eea",     # фиолетовый
        "error": "#ffa502",           # оранжевый
        "unavailable": "#ff4757",     # красный
        "test": "#747d8c"             # серый
    }
    return color_map.get(alert_type, "#747d8c")
