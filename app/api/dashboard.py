from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Any

from app.database import get_db
from app.models import App

router = APIRouter(tags=["Dashboard"])

# Настройка шаблонов
templates = Jinja2Templates(directory="app/templates")


def get_status_icon(status: str) -> str:
    """Возвращает иконку для статуса"""
    if status == "available":
        return "🟢"
    elif status == "unavailable":
        return "🔴"
    else:
        return "🟡"


def get_status_display(status: str) -> str:
    """Возвращает текстовое отображение статуса"""
    if status == "available":
        return "Доступно"
    elif status == "unavailable":
        return "Недоступно"
    elif status == "error":
        return "Ошибка"
    return "Не проверено"


@router.get("/", include_in_schema=False)
async def root_redirect():
    """Редирект с главной страницы на дашборд"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Публичная страница дашборда"""
    apps = db.query(App).order_by(App.created_at.desc()).all()

    # Подсчёт статистики
    total = len(apps)
    available = sum(1 for app in apps if app.last_status == "available")
    unavailable = sum(1 for app in apps if app.last_status == "unavailable")
    error = sum(1 for app in apps if app.last_status == "error")

    from app.config import settings
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "apps": apps,
            "total": total,
            "available": available,
            "unavailable": unavailable,
            "error": error,
            "get_status_icon": get_status_icon,
            "get_status_display": get_status_display,
            "version": settings.app_version,
        }
    )


@router.get("/alerts", response_class=HTMLResponse, include_in_schema=False)
async def alerts_page(request: Request):
    """Страница алертов"""
    return templates.TemplateResponse(
        "alerts.html",
        {"request": request}
    )


@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(request: Request):
    """Страница настроек"""
    return templates.TemplateResponse(
        "settings.html",
        {"request": request}
    )


@router.get("/api/v1/apps/statuses")
async def get_app_statuses(db: Session = Depends(get_db)):
    """
    JSON API для получения статусов всех приложений
    Используется дашбордом для автообновления
    """
    apps = db.query(App).order_by(App.created_at.desc()).all()

    result = []
    for app in apps:
        result.append({
            "id": app.id,
            "bundle_id": app.bundle_id,
            "app_id": app.app_id,
            "identifier": app.bundle_id or f"ID:{app.app_id}" if app.app_id else f"ID:{app.id}",
            "name": app.name,
            "version": app.version,
            "icon_url": app.icon_url,
            "last_status": app.last_status,
            "last_check_at": app.last_check_at.isoformat() if app.last_check_at else None,
            "status_icon": get_status_icon(app.last_status),
            "status_display": get_status_display(app.last_status),
            "last_error": app.last_error,
        })

    # Статистика
    total = len(apps)
    available = sum(1 for app in apps if app.last_status == "available")
    unavailable = sum(1 for app in apps if app.last_status == "unavailable")
    error = sum(1 for app in apps if app.last_status == "error")

    return {
        "apps": result,
        "stats": {
            "total": total,
            "available": available,
            "unavailable": unavailable,
            "error": error,
        },
        "last_updated": datetime.utcnow().isoformat()
    }
