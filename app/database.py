from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from app.config import settings

# Определение типа базы данных
is_sqlite = settings.database_url.startswith("sqlite")
is_postgresql = settings.database_url.startswith("postgresql")

# Настройки движка
if is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=False
    )
elif is_postgresql:
    engine = create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=10,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=False
    )
else:
    engine = create_engine(
        settings.database_url,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Зависимость для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Инициализация базы данных (создание таблиц)"""
    Base.metadata.create_all(bind=engine)


def check_and_init_db():
    """
    Проверка и инициализация базы данных
    Возвращает True если всё успешно
    """
    try:
        # Проверка подключения
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        
        # Создание таблиц
        init_db()
        
        return True
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
        return False
