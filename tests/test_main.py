import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import App, APIKey
from app.utils.security import generate_api_key


# Тестовая база данных в памяти
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Переопределяем зависимость get_db
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    """Фикстура для создания тестового клиента"""
    Base.metadata.create_all(bind=engine)
    try:
        yield TestClient(app)
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Фикстура для создания сессии БД"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def api_key(db_session):
    """Фикстура для создания тестового API ключа"""
    key = generate_api_key()
    db_key = APIKey(key=key, description="Test Key", is_active=True)
    db_session.add(db_key)
    db_session.commit()
    return key


# === Тесты здоровья ===

def test_health_check(client):
    """Тест проверки здоровья сервиса"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_redirect(client):
    """Тест редиректа с главной страницы"""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard"


# === Тесты дашборда ===

def test_dashboard_page(client):
    """Тест загрузки страницы дашборда"""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"App Store Monitor" in response.content


def test_get_app_statuses_empty(client):
    """Тест получения статусов без приложений"""
    response = client.get("/api/v1/apps/statuses")
    assert response.status_code == 200
    data = response.json()
    assert data["apps"] == []
    assert data["stats"]["total"] == 0


# === Тесты API ключей ===

def test_create_api_key(client, api_key):
    """Тест создания API ключа"""
    response = client.post(
        "/api/v1/keys",
        json={"description": "New Test Key"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == "New Test Key"
    assert data["is_active"] == True
    assert data["key"].startswith("sk_live_")


def test_list_api_keys(client, api_key):
    """Тест получения списка API ключей"""
    response = client.get(
        "/api/v1/keys",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_revoke_api_key(client, api_key, db_session):
    """Тест отзыва API ключа"""
    # Создаём второй ключ для отзыва
    key2 = generate_api_key()
    db_key = APIKey(key=key2, description="To Revoke", is_active=True)
    db_session.add(db_key)
    db_session.commit()
    
    response = client.delete(
        f"/api/v1/keys/{key2}",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 204
    
    # Проверяем что ключ отозван
    revoked_key = db_session.query(APIKey).filter(APIKey.key == key2).first()
    assert revoked_key.is_active == False


def test_api_without_key(client):
    """Тест доступа без API ключа"""
    response = client.get("/api/v1/apps")
    assert response.status_code == 401


def test_api_with_invalid_key(client):
    """Тест доступа с неверным API ключом"""
    response = client.get(
        "/api/v1/apps",
        headers={"X-API-Key": "invalid_key"}
    )
    assert response.status_code == 401


# === Тесты приложений ===

def test_add_app(client, api_key):
    """Тест добавления приложения"""
    response = client.post(
        "/api/v1/apps",
        json={"bundle_id": "com.example.testapp"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["bundle_id"] == "com.example.testapp"
    assert data["is_active"] == True


def test_add_app_duplicate(client, api_key, db_session):
    """Тест добавления дубликата приложения"""
    # Создаём приложение
    app = App(bundle_id="com.example.duplicate", is_active=True)
    db_session.add(app)
    db_session.commit()
    
    # Пытаемся добавить дубликат
    response = client.post(
        "/api/v1/apps",
        json={"bundle_id": "com.example.duplicate"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 400


def test_add_app_invalid_bundle_id(client, api_key):
    """Тест добавления приложения с неверным Bundle ID"""
    response = client.post(
        "/api/v1/apps",
        json={"bundle_id": "invalid bundle id!"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 422


def test_list_apps(client, api_key, db_session):
    """Тест получения списка приложений"""
    # Создаём тестовые приложения
    apps = [
        App(bundle_id="com.example.app1", name="App 1"),
        App(bundle_id="com.example.app2", name="App 2"),
    ]
    db_session.add_all(apps)
    db_session.commit()
    
    response = client.get(
        "/api/v1/apps",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_app(client, api_key, db_session):
    """Тест получения приложения по ID"""
    app = App(bundle_id="com.example.single", name="Single App")
    db_session.add(app)
    db_session.commit()
    
    response = client.get(
        f"/api/v1/apps/{app.id}",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["bundle_id"] == "com.example.single"


def test_get_app_not_found(client, api_key):
    """Тест получения несуществующего приложения"""
    response = client.get(
        "/api/v1/apps/99999",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 404


def test_delete_app(client, api_key, db_session):
    """Тест удаления приложения"""
    app = App(bundle_id="com.example.delete", is_active=True)
    db_session.add(app)
    db_session.commit()
    
    response = client.delete(
        f"/api/v1/apps/{app.id}",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 204
    
    # Проверяем что приложение удалено
    deleted_app = db_session.query(App).filter(App.id == app.id).first()
    assert deleted_app is None


def test_get_app_history(client, api_key, db_session):
    """Тест получения истории проверок"""
    from app.models import CheckHistory
    from datetime import datetime
    
    app = App(bundle_id="com.example.history", is_active=True)
    db_session.add(app)
    db_session.commit()
    
    history = CheckHistory(
        app_id=app.id,
        status="available",
        version="1.0.0",
        message="Приложение найдено",
        checked_at=datetime.utcnow()
    )
    db_session.add(history)
    db_session.commit()
    
    response = client.get(
        f"/api/v1/apps/{app.id}/history",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "available"
