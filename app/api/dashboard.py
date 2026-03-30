from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Any, Optional

from app.database import get_db
from app.models import App
from app.i18n import (
    LOCALE_COOKIE,
    alerts_js_bundle,
    dashboard_js_bundle,
    get_status_display as locale_status_display,
    locale_from_request,
    locale_tag_for_js,
    normalize_locale,
    safe_redirect_target,
    settings_js_bundle,
    t,
)

router = APIRouter(tags=["Dashboard"])

templates = Jinja2Templates(directory="app/templates")


def get_status_icon(status: str) -> str:
    """Возвращает иконку для статуса"""
    if status == "available":
        return "🟢"
    elif status == "unavailable":
        return "🔴"
    else:
        return "🟡"


def _t_bind(loc: str):
    def _translate(key: str, **kwargs: Any) -> str:
        return t(loc, key, **kwargs)

    return _translate


@router.get("/", include_in_schema=False)
async def root_redirect():
    """Редирект с главной страницы на дашборд"""
    return RedirectResponse(url="/dashboard")


@router.get("/locale/{lang}", include_in_schema=False)
async def set_ui_locale(lang: str, request: Request):
    """Установить язык интерфейса (cookie) и вернуться назад."""
    loc = normalize_locale(lang)
    target = safe_redirect_target(request)
    resp = RedirectResponse(url=target, status_code=302)
    resp.set_cookie(
        LOCALE_COOKIE,
        loc,
        max_age=365 * 24 * 3600,
        httponly=False,
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Публичная страница дашборда"""
    loc = locale_from_request(request)
    apps = db.query(App).order_by(App.created_at.desc()).all()

    total = len(apps)
    available = sum(1 for app in apps if app.last_status == "available")
    unavailable = sum(1 for app in apps if app.last_status == "unavailable")
    error = sum(1 for app in apps if app.last_status == "error")

    from app.config import settings

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "locale": loc,
            "t": _t_bind(loc),
            "i18n": dashboard_js_bundle(loc),
            "locale_tag": locale_tag_for_js(loc),
            "apps": apps,
            "total": total,
            "available": available,
            "unavailable": unavailable,
            "error": error,
            "get_status_icon": get_status_icon,
            "get_status_display": lambda s: locale_status_display(loc, s),
            "version": settings.app_version,
        },
    )


@router.get("/alerts", response_class=HTMLResponse, include_in_schema=False)
async def alerts_page(request: Request):
    """Страница алертов"""
    loc = locale_from_request(request)
    return templates.TemplateResponse(
        "alerts.html",
        {
            "request": request,
            "locale": loc,
            "t": _t_bind(loc),
            "i18n": alerts_js_bundle(loc),
            "locale_tag": locale_tag_for_js(loc),
        },
    )


@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(request: Request):
    """Страница настроек"""
    loc = locale_from_request(request)
    si = settings_js_bundle(loc)
    si["success_title"] = t(loc, "common.success_title")
    si["error_title"] = t(loc, "common.error")
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "locale": loc,
            "t": _t_bind(loc),
            "i18n": si,
            "locale_tag": locale_tag_for_js(loc),
        },
    )


@router.get("/api/v1/apps/statuses")
async def get_app_statuses(
    request: Request,
    db: Session = Depends(get_db),
    lang: Optional[str] = Query(None, description="Язык подписей: ru | en"),
):
    """
    JSON API для получения статусов всех приложений
    Используется дашбордом для автообновления
    """
    loc = normalize_locale(lang) if lang else locale_from_request(request)
    apps = db.query(App).order_by(App.created_at.desc()).all()

    result = []
    for app in apps:
        result.append(
            {
                "id": app.id,
                "bundle_id": app.bundle_id,
                "app_id": app.app_id,
                "identifier": app.bundle_id or f"ID:{app.app_id}" if app.app_id else f"ID:{app.id}",
                "name": app.name,
                "version": app.version,
                "description": app.description,
                "icon_url": app.icon_url,
                "last_status": app.last_status,
                "is_active": app.is_active,
                "last_check_at": app.last_check_at.isoformat() if app.last_check_at else None,
                "next_check_at": app.next_check_at.isoformat() if app.next_check_at else None,
                "status_icon": get_status_icon(app.last_status),
                "status_display": locale_status_display(loc, app.last_status),
                "last_error": app.last_error,
            }
        )

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
        "last_updated": datetime.utcnow().isoformat(),
        "locale": loc,
    }
