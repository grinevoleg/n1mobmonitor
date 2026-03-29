from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import App, CheckHistory, APIKey
from app.schemas import (
    AppCreate, AppResponse, AppStatusResponse,
    CheckHistoryResponse,
    APIKeyCreate, APIKeyResponse
)
from app.api.deps import get_api_key
from app.utils.security import create_api_key, revoke_api_key
from app.services.monitor import monitor_service

router = APIRouter(prefix="/api/v1", tags=["API"])


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
def get_app_history(app_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Получить историю проверок приложения"""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Приложение не найдено"
        )
    
    history = db.query(CheckHistory).filter(
        CheckHistory.app_id == app_id
    ).order_by(CheckHistory.checked_at.desc()).limit(100).all()
    
    return history


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


# === API Keys ===

@router.post("/keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
def create_key(key_data: APIKeyCreate, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Создать новый API ключ"""
    db_key = create_api_key(db, key_data.description)
    return db_key


@router.delete("/keys/{key}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(key: str, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Отозвать API ключ"""
    if not revoke_api_key(db, key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API ключ не найден"
        )
    return None


@router.get("/keys", response_model=List[APIKeyResponse])
def list_keys(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Получить список всех API ключей"""
    keys = db.query(APIKey).order_by(APIKey.created_at.desc()).all()
    return keys
