# 🍏 App Store Monitor

Сервис на FastAPI для безопасного мониторинга доступности iOS-приложений в App Store с публичным дашбордом и интеграцией с Google Sheets.

## Возможности

- ✅ **Мониторинг приложений** — проверка доступности по Bundle ID через iTunes Lookup API
- ✅ **Фоновый мониторинг** — автоматическая проверка каждые 10 минут
- ✅ **Публичный дашборд** — реальное время с автообновлением каждые 60 секунд
- ✅ **Google Sheets** — логирование изменений статуса в таблицу
- ✅ **API Key аутентификация** — защита API endpoints
- ✅ **Rate Limiting** — 100 запросов/час на ключ
- ✅ **История проверок** — хранение последних 100 проверок на приложение

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка

Скопируйте `.env.example` в `.env` и настройте:

```bash
cp .env.example .env
```

**Обязательные параметры:**
- `DATABASE_URL` — по умолчанию `sqlite:///./app_store_monitor.db`

**Опциональные параметры (Google Sheets):**
- `GOOGLE_CREDENTIALS` — JSON сервисного аккаунта Google
- `SPREADSHEET_ID` — ID таблицы Google Sheets
- `SHEET_NAME` — имя листа (по умолчанию `AppStoreMonitor`)

### 3. Запуск

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Откройте:
- **Дашборд**: http://localhost:8000/dashboard
- **API Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

## API Endpoints

### Публичные (без аутентификации)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/` | Редирект на дашборд |
| GET | `/dashboard` | HTML страница дашборда |
| GET | `/api/v1/apps/statuses` | JSON со статусами всех приложений |

### Защищённые (требуется API Key)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/apps` | Добавить приложение |
| GET | `/api/v1/apps` | Список всех приложений |
| GET | `/api/v1/apps/{id}` | Информация о приложении |
| POST | `/api/v1/apps/{id}/check` | Принудительная проверка |
| GET | `/api/v1/apps/{id}/history` | История проверок |
| DELETE | `/api/v1/apps/{id}` | Удалить приложение |
| POST | `/api/v1/keys` | Создать API ключ |
| GET | `/api/v1/keys` | Список API ключей |
| DELETE | `/api/v1/keys/{key}` | Отозвать ключ |

## Примеры использования

### 1. Создание API ключа

Первый ключ нужно создать вручную через API Docs или curl:

```bash
# Создаём первый ключ (без аутентификации для первого раза)
curl -X POST http://localhost:8000/api/v1/keys \
  -H "Content-Type: application/json" \
  -d '{"description": "Main API Key"}'
```

**В продакшене** создайте первый ключ через БД или добавьте endpoint без аутентификации.

### 2. Добавление приложения

```bash
curl -X POST http://localhost:8000/api/v1/apps \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_live_..." \
  -d '{"bundle_id": "com.example.myapp"}'
```

### 3. Получение статуса всех приложений

```bash
curl http://localhost:8000/api/v1/apps/statuses
```

### 4. Принудительная проверка

```bash
curl -X POST http://localhost:8000/api/v1/apps/1/check \
  -H "X-API-Key: sk_live_..."
```

## Настройка Google Sheets

### 1. Создайте сервисный аккаунт

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте проект или выберите существующий
3. Включите **Google Sheets API**
4. Создайте сервисный аккаунт
5. Скачайте JSON-ключ

### 2. Создайте таблицу

1. Создайте новую Google Sheet
2. Скопируйте ID таблицы из URL (между `/d/` и `/edit`)
3. Откройте доступ для сервисного аккаунта (email из JSON-ключа)

### 3. Настройте `.env`

```env
GOOGLE_CREDENTIALS={"type": "service_account", "project_id": "...", ...}
SPREADSHEET_ID=your_spreadsheet_id_here
SHEET_NAME=AppStoreMonitor
```

## Структура проекта

```
kwen/
├── app/
│   ├── main.py              # Точка входа FastAPI
│   ├── config.py            # Настройки
│   ├── database.py          # SQLAlchemy
│   ├── models.py            # ORM модели
│   ├── schemas.py           # Pydantic схемы
│   ├── utils/
│   │   └── security.py      # API ключи
│   ├── services/
│   │   ├── app_store.py     # iTunes API клиент
│   │   ├── sheets.py        # Google Sheets
│   │   └── monitor.py       # APScheduler
│   ├── api/
│   │   ├── routes.py        # REST endpoints
│   │   ├── deps.py          # Зависимости
│   │   └── dashboard.py     # Дашборд
│   ├── templates/
│   │   └── dashboard.html   # Шаблон дашборда
│   └── static/js/
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## Тестирование

```bash
pytest tests/ -v
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | URL базы данных | `sqlite:///./app_store_monitor.db` |
| `GOOGLE_CREDENTIALS` | JSON ключ Google | `None` |
| `SPREADSHEET_ID` | ID таблицы Google | `None` |
| `SHEET_NAME` | Имя листа | `AppStoreMonitor` |
| `RATE_LIMIT` | Лимит запросов/час | `100` |
| `MONITOR_INTERVAL` | Интервал проверки (мин) | `10` |

## Лицензия

MIT
