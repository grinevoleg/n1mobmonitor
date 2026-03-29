import logging
import smtplib
import httpx
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Setting, TelegramUser, UserNotificationSettings, UserRole, UserStatus
from app.config import settings

logger = logging.getLogger(__name__)


def get_approved_users_for_alert(db: Session, alert_type: str) -> List[Tuple[TelegramUser, UserNotificationSettings]]:
    """
    Получение списка пользователей которые должны получить уведомление
    
    Args:
        db: сессия БД
        alert_type: тип алерта
        
    Returns:
        список кортежей (user, settings)
    """
    users = db.query(TelegramUser).filter(
        TelegramUser.status == UserStatus.approved
    ).all()
    
    result = []
    for user in users:
        # Проверка настроек уведомлений
        if not user.notification_settings:
            continue
        
        settings = user.notification_settings
        
        # Проверка подписки на тип уведомления
        notify_map = {
            "status_change": settings.notify_status_change,
            "version_change": settings.notify_version_change,
            "error": settings.notify_error,
            "app_added": settings.notify_app_added,
            "unavailable": settings.notify_unavailable,
            "test": True  # Тестовые всегда отправляем
        }
        
        if notify_map.get(alert_type, False):
            result.append((user, settings))
    
    return result


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
    УСТАРЕЛА: Используется только для тестирования!
    Отправка Telegram уведомления (тестовое)
    """
    db = SessionLocal()
    try:
        settings_dict = get_all_settings(db)

        if settings_dict.get("telegram_enabled", "false").lower() != "true":
            logger.debug("Telegram уведомления отключены")
            return False

        bot_token = settings_dict.get("telegram_bot_token", "")
        
        # Получаем первого одобренного пользователя для теста
        test_user = db.query(TelegramUser).filter(
            TelegramUser.status == "approved"
        ).first()
        
        if not test_user:
            logger.warning("Нет одобренных пользователей для тестового уведомления")
            return False
        
        # Используем новую функцию для отправки
        return await send_telegram_alert_to_user(
            test_user, alert_type, app_name, app_identifier, old_value, new_value
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки Telegram: {e}")
        return False
    finally:
        db.close()
        
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
        
        # Парсинг значений для детальной информации
        old_data = json.loads(old_value) if old_value else {}
        new_data = json.loads(new_value) if new_value else {}
        
        # Формирование детального сообщения
        message = f"{emoji} *App Store Monitor*\n\n"
        
        if alert_type == "app_added":
            message += f"*🆕 Новое приложение в мониторинге*\n\n"
            message += f"*Название:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            if new_data.get('name'):
                message += f"*Полное имя:* `{new_data['name']}`\n"
            if new_data.get('version'):
                message += f"*Версия:* `{new_data['version']}`\n"
            if new_data.get('status'):
                status_text = {"available": "✅ Доступно", "unavailable": "❌ Недоступно", "error": "⚠️ Ошибка"}.get(new_data['status'], new_data['status'])
                message += f"*Статус:* {status_text}\n"
                
        elif alert_type == "version_change":
            message += f"*🔵 Обновление версии*\n\n"
            message += f"*Приложение:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            if old_data.get('version'):
                message += f"*Старая версия:* `{old_data['version']}`\n"
            if new_data.get('version'):
                message += f"*Новая версия:* `{new_data['version']}`\n"
                
        elif alert_type == "status_change":
            message += f"*🔴 Изменение статуса*\n\n"
            message += f"*Приложение:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            if old_data.get('status'):
                message += f"*Старый статус:* `{old_data['status']}`\n"
            if new_data.get('status'):
                status_text = {"available": "✅ Доступно", "unavailable": "❌ Недоступно", "error": "⚠️ Ошибка"}.get(new_data['status'], new_data['status'])
                message += f"*Новый статус:* {status_text}\n"
                
        elif alert_type == "error":
            message += f"*🟡 Ошибка проверки*\n\n"
            message += f"*Приложение:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            if new_data.get('error'):
                message += f"*Ошибка:* `{new_data['error']}`\n"
                
        elif alert_type == "unavailable":
            message += f"*🔴 Приложение недоступно*\n\n"
            message += f"*Приложение:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            message += f"*Статус:* ❌ Не найдено в App Store\n"
            
        elif alert_type == "test":
            message += f"*⚪ Тестовое уведомление*\n\n"
            message += f"Это тестовое сообщение от App Store Monitor.\n"
            message += f"Если вы видите это сообщение — уведомления работают!\n"
        
        message += f"\n_App Store Monitor_"
        
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
) -> dict:
    """
    Отправка уведомления всем пользователям через все каналы
    
    Returns:
        dict со статистикой отправок
    """
    db = SessionLocal()
    try:
        # Получаем пользователей для этого типа алерта
        users = get_approved_users_for_alert(db, alert_type)
        
        email_sent_count = 0
        telegram_sent_count = 0
        
        for user, user_settings in users:
            # Отправка Email
            try:
                # Для email используем глобальные настройки
                if await send_email_alert(alert_type, app_name, app_identifier, old_value, new_value):
                    email_sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send email to user {user.id}: {e}")
            
            # Отправка Telegram
            try:
                if await send_telegram_alert_to_user(user, alert_type, app_name, app_identifier, old_value, new_value):
                    telegram_sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send telegram to user {user.id}: {e}")
        
        return {
            "email_sent": email_sent_count,
            "telegram_sent": telegram_sent_count,
            "total_users": len(users)
        }
        
    finally:
        db.close()


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


async def send_telegram_alert_to_user(
    user: TelegramUser,
    alert_type: str,
    app_name: str,
    app_identifier: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None
) -> bool:
    """
    Отправка Telegram уведомления конкретному пользователю
    
    Args:
        user: модель пользователя
        alert_type: тип алерта
        app_name: название приложения
        app_identifier: идентификатор
        old_value: старое значение
        new_value: новое значение
        
    Returns:
        True если успешно
    """
    db = SessionLocal()
    try:
        settings_dict = get_all_settings(db)
        bot_token = settings_dict.get("telegram_bot_token", "")
        
        if not bot_token:
            return False
        
        # Формирование сообщения (такое же как в send_telegram_alert)
        emoji = {
            "status_change": "🔴", 
            "version_change": "🔵", 
            "error": "🟡",
            "app_added": "🆕",
            "unavailable": "🔴",
            "test": "⚪"
        }.get(alert_type, "⚪")
        
        # Парсинг значений
        old_data = json.loads(old_value) if old_value else {}
        new_data = json.loads(new_value) if new_value else {}
        
        message = f"{emoji} *App Store Monitor*\n\n"
        
        if alert_type == "app_added":
            message += f"*🆕 Новое приложение в мониторинге*\n\n"
            message += f"*Название:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            if new_data.get('name'):
                message += f"*Полное имя:* `{new_data['name']}`\n"
            if new_data.get('version'):
                message += f"*Версия:* `{new_data['version']}`\n"
            if new_data.get('status'):
                status_text = {"available": "✅ Доступно", "unavailable": "❌ Недоступно", "error": "⚠️ Ошибка"}.get(new_data['status'], new_data['status'])
                message += f"*Статус:* {status_text}\n"
        elif alert_type == "version_change":
            message += f"*🔵 Обновление версии*\n\n"
            message += f"*Приложение:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            if old_data.get('version'):
                message += f"*Старая версия:* `{old_data['version']}`\n"
            if new_data.get('version'):
                message += f"*Новая версия:* `{new_data['version']}`\n"
        elif alert_type == "status_change":
            message += f"*🔴 Изменение статуса*\n\n"
            message += f"*Приложение:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            if old_data.get('status'):
                message += f"*Старый статус:* `{old_data['status']}`\n"
            if new_data.get('status'):
                status_text = {"available": "✅ Доступно", "unavailable": "❌ Недоступно", "error": "⚠️ Ошибка"}.get(new_data['status'], new_data['status'])
                message += f"*Новый статус:* {status_text}\n"
        elif alert_type == "error":
            message += f"*🟡 Ошибка проверки*\n\n"
            message += f"*Приложение:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            if new_data.get('error'):
                message += f"*Ошибка:* `{new_data['error']}`\n"
        elif alert_type == "unavailable":
            message += f"*🔴 Приложение недоступно*\n\n"
            message += f"*Приложение:* `{app_name}`\n"
            message += f"*ID:* `{app_identifier}`\n"
            message += f"*Статус:* ❌ Не найдено в App Store\n"
        elif alert_type == "test":
            message += f"*⚪ Тестовое уведомление*\n\n"
            message += f"Это тестовое сообщение от App Store Monitor.\n"
        
        message += f"\n_App Store Monitor_"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": user.telegram_id,
            "text": message.strip(),
            "parse_mode": "Markdown"
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        
        logger.info(f"Telegram уведомление отправлено пользователю {user.telegram_id}: {alert_type}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки Telegram пользователю {user.telegram_id}: {e}")
        return False
    finally:
        db.close()
