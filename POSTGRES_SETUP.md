# 🐘 Настройка PostgreSQL для App Store Monitor

## Быстрая настройка

### 1. Установка PostgreSQL

#### macOS
```bash
brew install postgresql
brew services start postgresql
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

#### Windows
Скачайте с https://www.postgresql.org/download/windows/

### 2. Создание базы данных

```bash
# Вход в psql от имени postgres
sudo -u postgres psql

# Или на Windows
psql -U postgres
```

```sql
-- Создание базы данных
CREATE DATABASE app_store_monitor;

-- Создание пользователя
CREATE USER monitor_user WITH PASSWORD 'monitor_password';

-- Предоставление прав
GRANT ALL PRIVILEGES ON DATABASE app_store_monitor TO monitor_user;

-- Выход
\q
```

### 3. Настройка .env

```env
DATABASE_URL=postgresql://monitor_user:monitor_password@localhost:5432/app_store_monitor
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme
```

### 4. Запуск

#### Без Docker:
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### С Docker:
```bash
docker-compose up -d
```

## Проверка подключения

```bash
# Подключение к базе
psql -U monitor_user -d app_store_monitor -h localhost

# Проверка таблиц (после запуска приложения)
\dt
```

## Решение проблем

### Ошибка "connection refused"
```bash
# Проверьте что PostgreSQL запущен
brew services list  # macOS
sudo systemctl status postgresql  # Linux

# Запустите если остановлен
brew services start postgresql  # macOS
sudo systemctl start postgresql  # Linux
```

### Ошибка "authentication failed"
```bash
# Сбросьте пароль пользователя
sudo -u postgres psql
ALTER USER monitor_user WITH PASSWORD 'new_password';
\q

# Обновите .env
```

### Ошибка "database does not exist"
```bash
# Создайте базу данных
sudo -u postgres psql
CREATE DATABASE app_store_monitor;
\q
```

## Миграция с SQLite на PostgreSQL

1. Экспорт данных из SQLite:
```bash
sqlite3 app_store_monitor.db .dump > backup.sql
```

2. Создайте новую БД PostgreSQL и импортируйте:
```bash
# Потребуется конвертировать SQL синтаксис
# Или используйте инструменты миграции типа pgloader
```

3. Обновите `.env`:
```env
DATABASE_URL=postgresql://user:pass@localhost:5432/app_store_monitor
```

4. Перезапустите приложение - таблицы создадутся автоматически

## Production рекомендации

### Безопасность
- Используйте сложные пароли
- Ограничьте доступ к порту 5432
- Используйте SSL для подключений

### Производительность
- Настройте `shared_buffers` в postgresql.conf
- Используйте connection pooling (уже настроено в приложении)
- Регулярно делайте backup

### Backup
```bash
# Создать backup
pg_dump -U monitor_user app_store_monitor > backup.sql

# Восстановить
psql -U monitor_user app_store_monitor < backup.sql
```

## Ссылки

- Документация PostgreSQL: https://www.postgresql.org/docs/
- Docker образ: https://hub.docker.com/_/postgres
- pgAdmin (GUI): https://www.pgadmin.org/
