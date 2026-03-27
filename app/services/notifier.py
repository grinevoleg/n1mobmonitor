import logging
import smtplib
import httpx
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Setting
from app.config import settings

logger = logging.getLogger(__name__)


def get_setting(db: Session, key: str, default: str = "") -> str:
    """Получение настройки из БД"""
    setting = db.query(Setting).filter(Setting.key == key).first()
    return setting.value if setting else default


def get_all_settings(db: Session) -> Dict[str, str]:
    """Получение всех настроек"""
    settings_dict = {}
    for setting in db.query(Setting).all():
        settings_dict[setting.key] = setting.value
    return settings_dict


def update_setting(db: Session, key: str, value: str) -> Setting:
    """Обновление настройки"""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


async def send_email_alert(
    alert_type: str,
    app_name: str,
    app_identifier: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None
) -> bool:
    """
    Отправка Email уведомления об алерте
    
    Args:
        alert_type: тип алерта (status_change, version_change, error)
        app_name: название приложения
        app_identifier: bundle_id или app_id
        old_value: старое значение
        new_value: новое значение
        
    Returns:
        True если успешно
    """
    db = SessionLocal()
    try:
        settings_dict = get_all_settings(db)
        
        if settings_dict.get("email_enabled", "false").lower() != "true":
            logger.debug("Email уведомления отключены")
            return False
        
        smtp_host = settings_dict.get("smtp_host", "")
        smtp_port = int(settings_dict.get("smtp_port", "587"))
        smtp_user = settings_dict.get("smtp_user", "")
        smtp_password = settings_dict.get("smtp_password", "")
        alert_email = settings_dict.get("alert_email", "")
        
        if not all([smtp_host, smtp_user, smtp_password, alert_email]):
            logger.warning("Не все Email настройки заполнены")
            return False
        
        # Формирование темы и тела письма
        emoji = {
            "status_change": "🔴", 
            "version_change": "🔵", 
            "error": "🟡",
            "app_added": "🆕",
            "unavailable": "🔴",
            "test": "⚪"
        }.get(alert_type, "⚪")
        subject = f"{emoji} App Store Monitor: {alert_type} - {app_name}"
        
        body = f"""
        <html>
        <body>
            <h2>App Store Monitor - Уведомление</h2>
            <p><strong>Тип события:</strong> {alert_type}</p>
            <p><strong>Приложение:</strong> {app_name}</p>
            <p><strong>Идентификатор:</strong> {app_identifier}</p>
            <hr>
            <p><strong>Старое значение:</strong> {old_value or 'N/A'}</p>
            <p><strong>Новое значение:</strong> {new_value or 'N/A'}</p>
            <hr>
            <p><em>App Store Monitor</em></p>
        </body>
        </html>
        """
        
        # Создание письма
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = alert_email
        
        msg.attach(MIMEText(body, "html", "utf-8"))
        
        # Отправка
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        logger.info(f"Email уведомление отправлено: {alert_type} - {app_name}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки Email: {e}")
        return False
    finally:
        db.close()


async def send_telegram_alert(
    alert_type: str,
    app_name: str,
    app_identifier: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None
) -> bool:
    """
    Отправка Telegram уведомления об алерте
    
    Args:
        alert_type: тип алерта
        app_name: название приложения
        app_identifier: bundle_id или app_id
        old_value: старое значение
        new_value: новое значение
        
    Returns:
        True если успешно
    """
    db = SessionLocal()
    try:
        settings_dict = get_all_settings(db)
        
        if settings_dict.get("telegram_enabled", "false").lower() != "true":
            logger.debug("Telegram уведомления отключены")
            return False
        
        bot_token = settings_dict.get("telegram_bot_token", "")
        chat_id = settings_dict.get("telegram_chat_id", "")
        
        if not all([bot_token, chat_id]):
            logger.warning("Не все Telegram настройки заполнены")
            return False
        
        # Формирование сообщения
        emoji = {
            "status_change": "🔴", 
            "version_change": "🔵", 
            "error": "🟡",
            "app_added": "🆕",
            "unavailable": "🔴",
            "test": "⚪"
        }.get(alert_type, "⚪")
        
        message = f"""
{emoji} *App Store Monitor*

*Тип события:* `{alert_type}`
*Приложение:* {app_name}
*Идентификатор:* `{app_identifier}`

*Старое значение:* `{old_value or 'N/A'}`
*Новое значение:* `{new_value or 'N/A'}`
"""
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message.strip(),
            "parse_mode": "Markdown"
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        
        logger.info(f"Telegram уведомление отправлено: {alert_type} - {app_name}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки Telegram: {e}")
        return False
    finally:
        db.close()


async def send_alert(
    alert_type: str,
    app_name: str,
    app_identifier: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None
) -> tuple:
    """
    Отправка уведомления через все включённые каналы
    
    Returns:
        (email_sent, telegram_sent)
    """
    # Формирование заголовка в зависимости от типа
    type_titles = {
        "status_change": "Изменение статуса",
        "version_change": "Обновление версии",
        "name_change": "Изменение названия",
        "error": "Ошибка проверки",
        "unavailable": "Приложение недоступно",
        "app_added": "Новое приложение",
        "test": "Тестовое уведомление"
    }
    
    title = type_titles.get(alert_type, alert_type)
    full_message = f"{title}: {old_value or ''} → {new_value or ''}" if old_value else f"{title}"
    
    email_sent = await send_email_alert(alert_type, app_name, app_identifier, old_value, new_value)
    telegram_sent = await send_telegram_alert(alert_type, app_name, app_identifier, old_value, new_value)
    
    return email_sent, telegram_sent


# Функции для тестирования уведомлений
async def test_email_notification() -> tuple:
    """Тест Email уведомления"""
    return await send_email_alert(
        alert_type="test",
        app_name="Test Application",
        app_identifier="com.test.app",
        old_value="1.0.0",
        new_value="1.0.1"
    )


async def test_telegram_notification() -> tuple:
    """Тест Telegram уведомления"""
    return await send_telegram_alert(
        alert_type="test",
        app_name="Test Application",
        app_identifier="com.test.app",
        old_value="1.0.0",
        new_value="1.0.1"
    )
