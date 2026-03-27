import logging
import random
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models import App, CheckHistory
from app.services.app_store import app_store_client
from app.services.sheets import sheets_writer
from app.services.alert_detector import check_and_create_alerts
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
        Расчёт интервала до следующей проверки с рандомизацией
        
        Args:
            app_id: ID приложения
            
        Returns:
            Интервал в минутах с учётом jitter
        """
        base_interval = settings.monitor_interval
        jitter = settings.monitor_jitter
        
        # Случайное отклонение от базового интервала
        random_jitter = random.randint(-jitter, jitter)
        interval = max(5, base_interval + random_jitter)  # Минимум 5 минут
        
        return interval
    
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
            for app in apps:
                # Устанавливаем время в прошлое, чтобы проверка произошла сразу
                self._app_next_check[app.id] = datetime.utcnow() - timedelta(minutes=1)
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
        logger.info(f"Мониторинг запущен (интервал: ~{settings.monitor_interval}±{settings.monitor_jitter} мин)")
    
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
                await self._check_app(db, app)
                checked_count += 1
                
                # Планируем следующую проверку с рандомизацией
                interval = self._get_next_check_interval(app.id)
                self._app_next_check[app.id] = now + timedelta(minutes=interval)
                
                logger.debug(f"Приложение {app.bundle_id or app.app_id} проверено. Следующая проверка через {interval} мин")

            if checked_count > 0:
                logger.info(f"Проверено {checked_count} из {len(apps)} приложений")

        except Exception as e:
            logger.error(f"Ошибка при проверке приложений: {e}")
        finally:
            db.close()
    
    async def _check_app(self, db: Session, app: App, is_new_app: bool = False):
        """
        Проверка одного приложения

        Args:
            db: Сессия БД
            app: Модель приложения
            is_new_app: флаг нового приложения
        """
        try:
            # Запрос к Apple API по bundle_id или app_id
            if app.bundle_id:
                result = await app_store_client.lookup_by_bundle_id(app.bundle_id)
            elif app.app_id:
                result = await app_store_client.lookup_by_app_id(int(app.app_id))
            else:
                result = {"status": "error", "name": None, "version": None, "message": "Не указан bundle_id или app_id"}

            # Сохраняем предыдущий статус
            old_status = app.last_status

            # Обновляем информацию о приложении
            app.last_check_at = datetime.utcnow()
            app.last_status = result["status"]
            app.last_error = result["message"] if result["status"] == "error" else None

            if result["status"] == "available":
                app.name = result["name"]
                app.version = result["version"]
                # Обновляем bundle_id если он не был указан и не существует в другой записи
                if not app.bundle_id and result.get("bundle_id"):
                    existing = db.query(App).filter(
                        App.bundle_id == result["bundle_id"],
                        App.id != app.id
                    ).first()
                    if not existing:
                        app.bundle_id = result["bundle_id"]

            # Создаём запись в истории
            history = CheckHistory(
                app_id=app.id,
                status=result["status"],
                version=result.get("version"),
                message=result["message"],
                checked_at=datetime.utcnow()
            )
            db.add(history)

            # Логирование изменения статуса в Google Sheets
            if old_status != result["status"]:
                sheets_writer.log_status_change(
                    app_id=app.id,
                    bundle_id=app.bundle_id or app.app_id or str(app.id),
                    old_status=old_status,
                    new_status=result["status"],
                    version=result.get("version"),
                    message=result["message"]
                )
                logger.info(
                    f"Статус приложения {app.bundle_id or app.app_id} изменился: "
                    f"{old_status or 'N/A'} → {result['status']}"
                )

            db.commit()
            logger.info(f"Проверено {app.bundle_id or app.app_id}: {result['status']}")
            
            # Проверка на изменения и создание алертов (после коммита чтобы app имел обновлённые данные)
            alerts = check_and_create_alerts(db, app, result, is_new_app=is_new_app)
            db.commit()  # Коммит алертов
            
            # Отправка уведомлений для каждого алерта
            if alerts:
                app_identifier = app.bundle_id or app.app_id or str(app.id)
                app_name = app.name or app_identifier
                
                for alert in alerts:
                    await send_alert(
                        alert_type=alert.alert_type,
                        app_name=app_name,
                        app_identifier=app_identifier,
                        old_value=alert.old_value,
                        new_value=alert.new_value
                    )

        except Exception as e:
            logger.error(f"Ошибка проверки {app.bundle_id or app.app_id}: {e}")
            db.rollback()

            # Записываем ошибку
            app.last_check_at = datetime.utcnow()
            app.last_status = "error"
            app.last_error = str(e)

            history = CheckHistory(
                app_id=app.id,
                status="error",
                message=str(e),
                checked_at=datetime.utcnow()
            )
            db.add(history)
            db.commit()
    
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

            await self._check_app(db, app, is_new_app=is_new_app)

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
