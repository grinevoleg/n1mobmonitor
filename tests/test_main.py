import os

# До любых импортов app.* — Settings читает env при первом импорте config
os.environ["ADMIN_USERNAME"] = "test_admin"
os.environ["ADMIN_PASSWORD"] = "test_secret"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import App


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


app.dependency_overrides[get_db] = override_get_db

ADMIN_AUTH = ("test_admin", "test_secret")


@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    try:
        yield TestClient(app)
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_redirect(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard"


def test_dashboard_page(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"App Store Monitor" in response.content
    assert "Приложения".encode("utf-8") in response.content


def test_dashboard_locale_en(client):
    response = client.get("/dashboard", cookies={"locale": "en"})
    assert response.status_code == 200
    assert b"Applications" in response.content


def test_set_locale_redirect(client):
    response = client.get(
        "/locale/en",
        headers={"Referer": "http://testserver/dashboard"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.cookies.get("locale") == "en"
    assert response.headers.get("location", "").endswith("/dashboard")


def test_get_app_statuses_empty(client):
    response = client.get("/api/v1/apps/statuses")
    assert response.status_code == 200
    data = response.json()
    assert data["apps"] == []
    assert data["stats"]["total"] == 0


def test_get_app_statuses_lang_en(client):
    response = client.get("/api/v1/apps/statuses?lang=en")
    assert response.status_code == 200
    assert response.json().get("locale") == "en"


def test_api_without_auth(client):
    response = client.get("/api/v1/apps")
    assert response.status_code == 401


def test_api_with_invalid_basic_auth(client):
    response = client.get("/api/v1/apps", auth=("wrong", "wrong"))
    assert response.status_code == 401


def test_add_app(client):
    response = client.post(
        "/api/v1/apps",
        json={"bundle_id": "com.example.testapp"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["bundle_id"] == "com.example.testapp"
    assert data["is_active"] is True


def test_add_app_duplicate(client, db_session):
    app_row = App(bundle_id="com.example.duplicate", is_active=True)
    db_session.add(app_row)
    db_session.commit()

    response = client.post(
        "/api/v1/apps",
        json={"bundle_id": "com.example.duplicate"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 400


def test_add_app_invalid_bundle_id(client):
    response = client.post(
        "/api/v1/apps",
        json={"bundle_id": "invalid bundle id!"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 422


def test_list_apps(client, db_session):
    apps = [
        App(bundle_id="com.example.app1", name="App 1"),
        App(bundle_id="com.example.app2", name="App 2"),
    ]
    db_session.add_all(apps)
    db_session.commit()

    response = client.get("/api/v1/apps", auth=ADMIN_AUTH)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_app(client, db_session):
    row = App(bundle_id="com.example.single", name="Single App")
    db_session.add(row)
    db_session.commit()

    response = client.get(f"/api/v1/apps/{row.id}", auth=ADMIN_AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["bundle_id"] == "com.example.single"


def test_get_app_not_found(client):
    response = client.get("/api/v1/apps/99999", auth=ADMIN_AUTH)
    assert response.status_code == 404


def test_delete_app(client, db_session):
    row = App(bundle_id="com.example.delete", is_active=True)
    db_session.add(row)
    db_session.commit()
    app_id = row.id

    response = client.delete(f"/api/v1/apps/{app_id}", auth=ADMIN_AUTH)
    assert response.status_code == 204

    deleted = db_session.query(App).filter(App.id == app_id).first()
    assert deleted is None


def test_get_app_history(client, db_session):
    from app.models import CheckHistory
    from datetime import datetime

    row = App(bundle_id="com.example.history", is_active=True)
    db_session.add(row)
    db_session.commit()

    history = CheckHistory(
        app_id=row.id,
        status="available",
        version="1.0.0",
        message="Приложение найдено",
        checked_at=datetime.utcnow(),
    )
    db_session.add(history)
    db_session.commit()

    response = client.get(f"/api/v1/apps/{row.id}/history", auth=ADMIN_AUTH)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "available"


def test_get_app_history_only_changes(client, db_session):
    from app.models import CheckHistory
    from datetime import datetime
    from app.services.change_log import build_audit_json

    row = App(bundle_id="com.example.honly", is_active=True)
    db_session.add(row)
    db_session.commit()

    snap = {
        "last_status": "available",
        "name": "App",
        "version": "1.0",
        "icon_url": None,
        "description": None,
        "bundle_id": None,
        "app_id": None,
    }
    audit_no = build_audit_json(
        snap, snap, check_kind="scheduled", api_status="available", api_message="ok"
    )
    snap_after = {**snap, "version": "2.0"}
    audit_yes = build_audit_json(
        snap, snap_after, check_kind="scheduled", api_status="available", api_message="ok"
    )

    db_session.add(
        CheckHistory(
            app_id=row.id,
            status="available",
            version="1.0",
            message="m",
            audit_json=audit_no,
            checked_at=datetime.utcnow(),
        )
    )
    db_session.add(
        CheckHistory(
            app_id=row.id,
            status="available",
            version="2.0",
            message="m2",
            audit_json=audit_yes,
            checked_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    r_all = client.get(f"/api/v1/apps/{row.id}/history?limit=10", auth=ADMIN_AUTH)
    assert r_all.status_code == 200
    assert len(r_all.json()) == 2

    r_ch = client.get(
        f"/api/v1/apps/{row.id}/history?limit=10&only_changes=true",
        auth=ADMIN_AUTH,
    )
    assert r_ch.status_code == 200
    body = r_ch.json()
    assert len(body) == 1
    assert body[0]["audit"] is not None
    assert body[0]["audit"]["had_changes"] is True
