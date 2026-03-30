import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import JSONB
from typing import List

from app.database import get_db
from app.models import App, CheckHistory
from app.schemas import (
    AppCreate, AppResponse,
    CheckHistoryResponse,
)
from app.api.deps import get_admin_user
from app.services.monitor import monitor_service

router = APIRouter(prefix="/api/v1", tags=["API"])


def _history_filter_only_changes(q, db: Session):
    """Фильтр по audit.had_changes в JSON (SQLite JSON1 / PostgreSQL JSONB)."""
    q = q.filter(CheckHistory.audit_json.isnot(None)).filter(CheckHistory.audit_json != "")
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        j = cast(CheckHistory.audit_json, JSONB)
        return q.filter(j["had_changes"].astext == "true")
    jc = func.json_extract(CheckHistory.audit_json, "$.had_changes")
    return q.filter(or_(jc == 1, jc == "true"))


# === Apps ===

@router.post("/apps", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
def add_app(app_data: AppCreate, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Добавить приложение для мониторинга (по bundle_id или app_id)"""
    # Проверка на дубликат по bundle_id
    if app_data.bundle_id:
        existing = db.query(App).filter(App.bundle_id == app_data.bundle_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Приложение с таким Bundle ID уже существует"
            )
    
    # Проверка на дубликат по app_id
    if app_data.app_id:
        existing = db.query(App).filter(App.app_id == str(app_data.app_id)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Приложение с таким Apple ID уже существует"
            )

    db_app = App(
        bundle_id=app_data.bundle_id,
        app_id=str(app_data.app_id) if app_data.app_id else None,
        is_active=True
    )
    db.add(db_app)
    db.commit()
    db.refresh(db_app)

    return db_app


@router.get("/apps", response_model=List[AppResponse])
def list_apps(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Получить список всех приложений"""
    apps = db.query(App).order_by(App.created_at.desc()).all()
    return apps


@router.get("/apps/{app_id}", response_model=AppResponse)
def get_app(app_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Получить информацию о приложении"""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Приложение не найдено"
        )
    return app


@router.post("/apps/{app_id}/check", response_model=AppResponse)
async def check_app(app_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Принудительная проверка статуса приложения"""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Приложение не найдено"
        )
    
    result = await monitor_service.check_single_app(app_id)
    
    if "error" in result and len(result) == 1:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"]
        )
    
    db.refresh(app)
    return app


@router.get("/apps/{app_id}/history", response_model=List[CheckHistoryResponse])
def get_app_history(
    app_id: int,
    limit: int = Query(100, ge=1, le=500),
    only_changes: bool = Query(
        False,
        description="Только записи, где в audit было изменение карточки (had_changes)",
    ),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    """История проверок с полем audit (снимки до/после и список изменений)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Приложение не найдено"
        )

    q = db.query(CheckHistory).filter(CheckHistory.app_id == app_id)
    if only_changes:
        q = _history_filter_only_changes(q, db)
    rows = q.order_by(CheckHistory.checked_at.desc()).limit(limit).all()

    result: List[CheckHistoryResponse] = []
    for h in rows:
        audit = None
        if h.audit_json:
            try:
                audit = json.loads(h.audit_json)
            except json.JSONDecodeError:
                audit = None
        result.append(
            CheckHistoryResponse(
                id=h.id,
                app_id=h.app_id,
                status=h.status,
                version=h.version,
                message=h.message,
                checked_at=h.checked_at,
                audit=audit,
            )
        )
    return result


@router.delete("/apps/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app(app_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Удалить приложение из мониторинга"""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Приложение не найдено"
        )
    
    db.delete(app)
    db.commit()
    
    return None
