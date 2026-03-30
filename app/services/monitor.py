import logging
import random
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import App, CheckHistory
from app.services.app_store import app_store_client
from app.services.sheets import sheets_writer
from app.services.change_log import (
    snapshot_from_app,
    format_changes_line,
    build_audit_json,
)
from app.services.alert_detector import check_and_create_alerts
from app.services.notifier import get_setting
from app.services.notifier import send_alert
from app.config import settings

logger = logging.getLogger(__name__)


class MonitorService:
    """Сервис фонового мониторинга приложений"""
    
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._running = False
        self._app_next_check: dict = {}  # Хранение времени следующей проверки для каждого приложения
    
    def _get_next_check_interval(self, app_id: int) -> int:
        """
        Интервал до следующей проверки (минуты): из БД настроек monitor_interval / monitor_jitter,
        с запасом из .env при ошибке парсинга. Джиттер не больше базового интервала.
        """
        _ = app_id
        db = SessionLocal()
        try:
            try:
                base_interval = int(
                    get_setting(db, "monitor_interval", str(settings.monitor_interval))
                )
                jitter = int(
                    get_setting(db, "monitor_jitter", str(settings.monitor_jitter))
                )
            except ValueError:
                base_interval = settings.monitor_interval
                jitter = settings.monitor_jitter
        finally:
            db.close()

        base_interval = max(5, min(base_interval, 24 * 60))
        jitter = max(0, min(jitter, base_interval))
        random_jitter = random.randint(-jitter, jitter)
        return max(5, base_interval + random_jitter)

    def clear_next_schedule(self, app_id: int) -> None:
        """Снять приложение с расписания (выключен мониторинг)."""
        self._app_next_check.pop(app_id, None)

    def prime_app_schedule(self, app_id: int) -> None:
        """Следующая фоновая проверка как можно скорее (включили мониторинг)."""
        self._app_next_check[app_id] = datetime.utcnow() - timedelta(minutes=1)

    def _persist_next_check(self, db: Session, app: App, from_time: datetime) -> None:
        """Записать в БД и в память время следующей проверки."""
        if not app.is_active:
            app.next_check_at = None
            self._app_next_check.pop(app.id, None)
            db.commit()
            return
        interval = self._get_next_check_interval(app.id)
        next_dt = from_time + timedelta(minutes=interval)
        self._app_next_check[app.id] = next_dt
        app.next_check_at = next_dt
        db.commit()
    
    def start(self):
        """Запуск планировщика"""
        if self._running:
            logger.warning("Мониторинг уже запущен")
            return
        
        # Инициализируем время проверки для всех существующих приложений
        # Чтобы при старте все приложения проверились сразу
        db = SessionLocal()
        try:
            apps = db.query(App).filter(App.is_active == True).all()
            now = datetime.utcnow()
            for app in apps:
                if app.next_check_at and app.next_check_at > now:
                    self._app_next_check[app.id] = app.next_check_at
                else:
                    self._app_next_check[app.id] = now - timedelta(minutes=1)
            logger.info(f"Инициализировано {len(apps)} приложений для мониторинга")
        finally:
            db.close()
        
        self.scheduler = AsyncIOScheduler()
        
        # Добавляем задачу проверки каждую минуту
        # Но каждое приложение проверяется только когда придёт его время
        self.scheduler.add_job(
            self._check_all_apps,
            trigger=IntervalTrigger(minutes=1),
            id="check_all_apps",
            name="Проверка всех приложений",
            replace_existing=True
        )
        
        self.scheduler.start()
        self._running = True
        logger.info(
            "Мониторинг запущен: тик каждую минуту; интервал и джиттер для каждого приложения "
            "читаются из настроек БД (monitor_interval / monitor_jitter), с запасом из .env"
        )
    
    def stop(self):
        """Остановка планировщика"""
        if self.scheduler:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Мониторинг остановлен")
    
    async def _check_all_apps(self):
        """Проверка всех активных приложений (только тех, что готовы к проверке)"""
        db = SessionLocal()
        try:
            # Получаем все активные приложения
            apps = db.query(App).filter(App.is_active == True).all()
            
            now = datetime.utcnow()
            checked_count = 0

            for app in apps:
                # Проверяем, пришло ли время для этого приложения
                next_check = self._app_next_check.get(app.id)
                
                if next_check and now < next_check:
                    continue  # Ещё не время для проверки
                
                # Проверяем приложение
                await self._check_app(db, app, check_kind="scheduled")
                checked_count += 1

                db.refresh(app)
                self._persist_next_check(db, app, datetime.utcnow())

                logger.debug(
                    f"Приложение {app.bundle_id or app.app_id} проверено. "
                    f"Следующая проверка: {app.next_check_at}"
                )

            if checked_count > 0:
                logger.info(f"Проверено {checked_count} из {len(apps)} приложений")

        except Exception as e:
            logger.error(f"Ошибка при проверке приложений: {e}")
        finally:
            db.close()
    
    async def _check_app(
        self,
        db: Session,
        app: App,
        is_new_app: bool = False,
        check_kind: str = "scheduled",
    ):
        """
        Проверка одного приложения.

        check_kind: scheduled — фоновый цикл; manual — кнопка/API.
        Каждая проверка пишет запись в check_history с audit_json (снимки и список изменений).
        """
        try:
            snapshot_before = snapshot_from_app(app)

            if app.bundle_id:
                result = await app_store_client.lookup_by_bundle_id(app.bundle_id)
            elif app.app_id:
                result = await app_store_client.lookup_by_app_id(int(app.app_id))
            else:
                result = {"status": "error", "name": None, "version": None, "message": "Не указан bundle_id или app_id"}

            old_status = snapshot_before["last_status"]

            app.last_check_at = datetime.utcnow()
            app.last_status = result["status"]
            app.last_error = result["message"] if result["status"] == "error" else None

            if result["status"] == "available":
                app.name = result["name"]
                app.version = result["version"]
                app.icon_url = result.get("icon_url")
                app.description = result.get("description")
                if not app.bundle_id and result.get("bundle_id"):
                    existing = db.query(App).filter(
                        App.bundle_id == result["bundle_id"],
                        App.id != app.id
                    ).first()
                    if not existing:
                        app.bundle_id = result["bundle_id"]
                if result.get("app_id") and not app.app_id:
                    app.app_id = str(result["app_id"])

            snapshot_after = snapshot_from_app(app)
            history_msg = result["message"]
            changes_line = format_changes_line(snapshot_before, snapshot_after)
            if changes_line:
                history_msg = f"{history_msg} | Изменения: {changes_line}"

            audit = build_audit_json(
                snapshot_before,
                snapshot_after,
                check_kind=check_kind,
                api_status=result["status"],
                api_message=result.get("message"),
            )

            history = CheckHistory(
                app_id=app.id,
                status=result["status"],
                version=result.get("version"),
                message=history_msg,
                audit_json=audit,
                checked_at=datetime.utcnow(),
            )
            db.add(history)

            if old_status != result["status"]:
                sheets_writer.log_status_change(
                    app_id=app.id,
                    bundle_id=app.bundle_id or app.app_id or str(app.id),
                    old_status=old_status,
                    new_status=result["status"],
                    version=result.get("version"),
                    message=result["message"],
                )
                logger.info(
                    f"Статус приложения {app.bundle_id or app.app_id} изменился: "
                    f"{old_status or 'N/A'} → {result['status']}"
                )

            db.commit()
            logger.info(f"Проверено {app.bundle_id or app.app_id}: {result['status']}")

            alerts = check_and_create_alerts(
                db, app, result, snapshot_before, snapshot_after, is_new_app=is_new_app
            )
            db.commit()

            if alerts:
                app_identifier = app.bundle_id or app.app_id or str(app.id)
                app_name = app.name or app_identifier

                for alert in alerts:
                    await send_alert(
                        alert_type=alert.alert_type,
                        app_name=app_name,
                        app_identifier=app_identifier,
                        old_value=alert.old_value,
                        new_value=alert.new_value,
                    )

        except Exception as e:
            logger.error(f"Ошибка проверки {app.bundle_id or app.app_id}: {e}")
            db.rollback()
            db.refresh(app)
            snapshot_before = snapshot_from_app(app)

            app.last_check_at = datetime.utcnow()
            app.last_status = "error"
            app.last_error = str(e)

            snapshot_after = snapshot_from_app(app)
            err_result = {"status": "error", "message": str(e)}
            history_msg = str(e)
            cl = format_changes_line(snapshot_before, snapshot_after)
            if cl:
                history_msg = f"{history_msg} | Изменения: {cl}"

            audit = build_audit_json(
                snapshot_before,
                snapshot_after,
                check_kind=check_kind,
                api_status="error",
                api_message=str(e),
            )

            history = CheckHistory(
                app_id=app.id,
                status="error",
                message=history_msg,
                audit_json=audit,
                checked_at=datetime.utcnow(),
            )
            db.add(history)
            db.commit()

            alerts = check_and_create_alerts(
                db, app, err_result, snapshot_before, snapshot_after, is_new_app=False
            )
            db.commit()

            if alerts:
                app_identifier = app.bundle_id or app.app_id or str(app.id)
                app_name = app.name or app_identifier
                for alert in alerts:
                    await send_alert(
                        alert_type=alert.alert_type,
                        app_name=app_name,
                        app_identifier=app_identifier,
                        old_value=alert.old_value,
                        new_value=alert.new_value,
                    )
    
    async def check_single_app(self, app_id: int, is_new_app: bool = False) -> dict:
        """
        Принудительная проверка одного приложения

        Args:
            app_id: ID приложения
            is_new_app: флаг нового приложения (для уведомлений)

        Returns:
            dict с результатом проверки
        """
        db = SessionLocal()
        try:
            app = db.query(App).filter(App.id == app_id).first()
            if not app:
                return {"error": "Приложение не найдено"}

            await self._check_app(
                db, app, is_new_app=is_new_app, check_kind="manual"
            )

            db.refresh(app)
            if app.is_active:
                self._persist_next_check(db, app, datetime.utcnow())

            return {
                "status": app.last_status,
                "name": app.name,
                "version": app.version,
                "last_check_at": app.last_check_at,
                "last_error": app.last_error
            }

        except Exception as e:
            logger.error(f"Ошибка принудительной проверки: {e}")
            return {"error": str(e)}
        finally:
            db.close()


# Singleton экземпляр
monitor_service = MonitorService()
