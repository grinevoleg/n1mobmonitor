import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)


class GoogleSheetsWriter:
    """Сервис для записи данных в Google Sheets"""
    
    def __init__(self):
        self._client = None
        self._spreadsheet = None
        self._worksheet = None
        self._initialized = False
    
    def _init_client(self) -> bool:
        """Инициализация клиента Google Sheets"""
        if self._initialized:
            return self._client is not None
        
        if not settings.google_credentials or not settings.spreadsheet_id:
            logger.warning("Google Sheets не настроен: отсутствуют credentials или spreadsheet_id")
            return False
        
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            # Парсим credentials из JSON строки
            credentials_info = json.loads(settings.google_credentials)
            
            # Создаём credentials
            credentials = Credentials.from_service_account_info(
                credentials_info,
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            
            # Создаём клиент
            self._client = gspread.authorize(credentials)
            
            # Открываем таблицу
            self._spreadsheet = self._client.open_by_key(settings.spreadsheet_id)
            
            # Получаем или создаём лист
            try:
                self._worksheet = self._spreadsheet.worksheet(settings.sheet_name)
            except gspread.WorksheetNotFound:
                self._worksheet = self._spreadsheet.add_worksheet(
                    title=settings.sheet_name,
                    rows=1000,
                    cols=10
                )
                # Создаём заголовок
                self._worksheet.append_row([
                    "Timestamp", "App ID", "Bundle ID", "Status", "Version", "Message"
                ])
            
            self._initialized = True
            logger.info(f"Google Sheets инициализирован: {settings.spreadsheet_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации Google Sheets: {e}")
            return False
    
    def append_status(self, app_id: int, bundle_id: str, status: str, 
                      version: Optional[str], message: str) -> bool:
        """
        Добавление записи о статусе приложения
        
        Args:
            app_id: ID приложения в БД
            bundle_id: Bundle ID приложения
            status: Статус (available/unavailable/error)
            version: Версия приложения
            message: Сообщение/ошибка
            
        Returns:
            True если успешно
        """
        if not self._init_client():
            return False
        
        try:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
            self._worksheet.append_row([
                timestamp,
                str(app_id),
                bundle_id,
                status,
                version or "",
                message
            ])
            
            logger.info(f"Запись в Google Sheets: {bundle_id} - {status}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка записи в Google Sheets: {e}")
            return False
    
    def log_status_change(self, app_id: int, bundle_id: str, 
                          old_status: Optional[str], new_status: str,
                          version: Optional[str], message: str) -> bool:
        """
        Логирование изменения статуса
        
        Args:
            app_id: ID приложения в БД
            bundle_id: Bundle ID приложения
            old_status: Предыдущий статус
            new_status: Новый статус
            version: Версия приложения
            message: Сообщение
        """
        if old_status != new_status:
            change_message = f"Статус изменился: {old_status or 'N/A'} → {new_status}. {message}"
            return self.append_status(app_id, bundle_id, new_status, version, change_message)
        
        return True


# Singleton экземпляр
sheets_writer = GoogleSheetsWriter()
