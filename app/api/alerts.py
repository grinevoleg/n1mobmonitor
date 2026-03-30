from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Alert, App
from app.schemas import AlertResponse, AlertStats
from app.api.deps import get_admin_user
from app.services.alert_detector import get_alert_emoji

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


def alert_to_response(alert: Alert) -> AlertResponse:
    """Конвертация модели Alert в схему ответа"""
    return AlertResponse(
        id=alert.id,
        app_id=alert.app_id,
        app_name=alert.app.name if alert.app else None,
        app_identifier=alert.app.bundle_id or alert.app.app_id if alert.app else None,
        alert_type=alert.alert_type,
        old_value=alert.old_value,
        new_value=alert.new_value,
        message=alert.message,
        is_read=alert.is_read,
        created_at=alert.created_at,
        alert_emoji=get_alert_emoji(alert.alert_type)
    )


@router.get("", response_model=List[AlertResponse])
def get_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = False,
    alert_type: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Получить список алертов с пагинацией"""
    query = db.query(Alert).order_by(Alert.created_at.desc())
    
    if unread_only:
        query = query.filter(Alert.is_read == False)
    
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    
    alerts = query.offset(skip).limit(limit).all()
    return [alert_to_response(alert) for alert in alerts]


@router.get("/unread", response_model=List[AlertResponse])
def get_unread_alerts(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Получить непрочитанные алерты"""
    alerts = db.query(Alert).filter(Alert.is_read == False).order_by(Alert.created_at.desc()).all()
    return [alert_to_response(alert) for alert in alerts]


@router.get("/stats", response_model=AlertStats)
def get_alert_stats(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Получить статистику алертов"""
    total = db.query(Alert).count()
    unread = db.query(Alert).filter(Alert.is_read == False).count()
    
    # Статистика по типам
    by_type = {}
    by_type_unread = {}
    
    alert_types = [
        "status_change",
        "version_change",
        "name_change",
        "description_change",
        "icon_change",
        "bundle_id_change",
        "app_id_change",
        "error",
        "unavailable",
        "app_added",
    ]
    for alert_type in alert_types:
        by_type[alert_type] = db.query(Alert).filter(Alert.alert_type == alert_type).count()
        by_type_unread[alert_type] = db.query(Alert).filter(
            Alert.alert_type == alert_type,
            Alert.is_read == False
        ).count()
    
    return AlertStats(
        total=total,
        unread=unread,
        by_type=by_type,
        by_type_unread=by_type_unread
    )


@router.post("/{alert_id}/read")
def mark_as_read(
    alert_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Отметить алерт как прочитанный"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Алерт не найден")
    
    alert.is_read = True
    db.commit()
    return {"status": "ok", "message": "Алерт отмечен как прочитанный"}


@router.post("/read-all")
def mark_all_as_read(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Отметить все алерты как прочитанные"""
    db.query(Alert).filter(Alert.is_read == False).update({"is_read": True})
    db.commit()
    return {"status": "ok", "message": "Все алерты отмечены как прочитанные"}


@router.delete("/{alert_id}", status_code=204)
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user)
):
    """Удалить алерт"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Алерт не найден")
    
    db.delete(alert)
    db.commit()
    return None
