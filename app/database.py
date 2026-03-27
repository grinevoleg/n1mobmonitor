from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Определение типа базы данных
is_sqlite = settings.database_url.startswith("sqlite")

# Настройки движка
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if is_sqlite else {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True
    },
    echo=False  # Включить для отладки SQL запросов
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
