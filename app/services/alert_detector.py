import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import Alert, App
logger = logging.getLogger(__name__)

# Макс. длина текста в JSON алерта (описание и т.д.)
_TEXT_ALERT_MAX = 800


def _truncate_for_alert(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    if len(s) <= _TEXT_ALERT_MAX:
        return s
    return s[: _TEXT_ALERT_MAX] + "…"


def check_and_create_alerts(
    db: Session,
    app: App,
    result: Dict[str, Any],
    snapshot_before: Dict[str, Any],
    snapshot_after: Dict[str, Any],
    is_new_app: bool = False,
) -> List[Alert]:
    """
    Создание алертов по разнице snapshot_before → snapshot_after и результату API.
    snapshot_* — до и после обновления полей модели App в памяти (до commit алертов).
    """
    alerts: List[Alert] = []
    app_identifier = app.bundle_id or app.app_id or str(app.id)
    app_name = snapshot_after.get("name") or snapshot_before.get("name") or app_identifier

    old_s = snapshot_before.get("last_status")
    new_s = snapshot_after.get("last_status")

    # 0. Новое приложение в мониторинге
    if is_new_app and new_s is not None:
        status_emoji = {"available": "🟢", "unavailable": "🔴", "error": "🟡"}.get(new_s, "⚪")
        alert = Alert(
            app_id=app.id,
            alert_type="app_added",
            old_value=None,
            new_value=json.dumps(
                {
                    "status": new_s,
                    "name": result.get("name"),
                    "version": result.get("version"),
                    "bundle_id": snapshot_after.get("bundle_id"),
                    "app_id": snapshot_after.get("app_id"),
                },
                ensure_ascii=False,
            ),
            message=f"Приложение добавлено в мониторинг. Статус: {status_emoji} {new_s}",
            created_at=datetime.utcnow(),
        )
        db.add(alert)
        alerts.append(alert)
        logger.info(f"Алерт app_added для {app_name}")
        return alerts

    if old_s != new_s and new_s is not None:
        # Переход в ошибку API / проверки
        if new_s == "error":
            err_msg = result.get("message") or "Неизвестная ошибка"
            alert = Alert(
                app_id=app.id,
                alert_type="error",
                old_value=json.dumps({"status": old_s}, ensure_ascii=False),
                new_value=json.dumps({"status": new_s, "error": err_msg}, ensure_ascii=False),
                message=f"Ошибка проверки: {err_msg}",
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            alerts.append(alert)
            logger.warning(f"Алерт error для {app_name}: {err_msg}")
        # Пропало из App Store
        elif new_s == "unavailable":
            alert = Alert(
                app_id=app.id,
                alert_type="unavailable",
                old_value=json.dumps({"status": old_s}, ensure_ascii=False),
                new_value=json.dumps({"status": new_s}, ensure_ascii=False),
                message="Приложение не найдено в App Store",
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            alerts.append(alert)
            logger.warning(f"Алерт unavailable для {app_name}")
        # Любая другая смена статуса (в т.ч. снова available)
        else:
            alert = Alert(
                app_id=app.id,
                alert_type="status_change",
                old_value=json.dumps({"status": old_s}, ensure_ascii=False),
                new_value=json.dumps(
                    {
                        "status": new_s,
                        "name": snapshot_after.get("name"),
                        "version": snapshot_after.get("version"),
                    },
                    ensure_ascii=False,
                ),
                message=f"Статус изменился: {old_s or 'N/A'} → {new_s}",
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            alerts.append(alert)
            logger.info(f"Алерт status_change для {app_name}: {old_s} → {new_s}")

    # Метаданные (только если карточка в состоянии available — актуальные данные из API)
    if snapshot_after.get("last_status") == "available" and not is_new_app:
        ov, nv = snapshot_before.get("version"), snapshot_after.get("version")
        if ov != nv and (ov is not None or nv is not None):
            alert = Alert(
                app_id=app.id,
                alert_type="version_change",
                old_value=json.dumps({"version": ov}, ensure_ascii=False),
                new_value=json.dumps({"version": nv, "name": snapshot_after.get("name")}, ensure_ascii=False),
                message=f"Версия изменилась: {ov or 'N/A'} → {nv or 'N/A'}",
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            alerts.append(alert)
            logger.info(f"Алерт version_change для {app_name}: {ov} → {nv}")

        on, nn = snapshot_before.get("name"), snapshot_after.get("name")
        if on != nn and (on is not None or nn is not None):
            alert = Alert(
                app_id=app.id,
                alert_type="name_change",
                old_value=json.dumps({"name": on}, ensure_ascii=False),
                new_value=json.dumps({"name": nn}, ensure_ascii=False),
                message=f"Название изменилось: {on or 'N/A'} → {nn or 'N/A'}",
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            alerts.append(alert)

        oi, ni = snapshot_before.get("icon_url"), snapshot_after.get("icon_url")
        if oi != ni and (oi is not None or ni is not None):
            alert = Alert(
                app_id=app.id,
                alert_type="icon_change",
                old_value=json.dumps({"icon_url": oi}, ensure_ascii=False),
                new_value=json.dumps({"icon_url": ni}, ensure_ascii=False),
                message="Изменилась ссылка на иконку в App Store",
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            alerts.append(alert)

        od, nd = snapshot_before.get("description"), snapshot_after.get("description")
        if od != nd and (od is not None or nd is not None):
            alert = Alert(
                app_id=app.id,
                alert_type="description_change",
                old_value=json.dumps({"description": _truncate_for_alert(od)}, ensure_ascii=False),
                new_value=json.dumps({"description": _truncate_for_alert(nd)}, ensure_ascii=False),
                message="Изменилось описание приложения в App Store",
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            alerts.append(alert)

        ob, nb = snapshot_before.get("bundle_id"), snapshot_after.get("bundle_id")
        if ob != nb and (ob is not None or nb is not None):
            alert = Alert(
                app_id=app.id,
                alert_type="bundle_id_change",
                old_value=json.dumps({"bundle_id": ob}, ensure_ascii=False),
                new_value=json.dumps({"bundle_id": nb}, ensure_ascii=False),
                message=f"Bundle ID: {ob or 'N/A'} → {nb or 'N/A'}",
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            alerts.append(alert)

        oa, na = snapshot_before.get("app_id"), snapshot_after.get("app_id")
        if oa != na and (oa is not None or na is not None):
            alert = Alert(
                app_id=app.id,
                alert_type="app_id_change",
                old_value=json.dumps({"app_id": oa}, ensure_ascii=False),
                new_value=json.dumps({"app_id": na}, ensure_ascii=False),
                message=f"Apple ID: {oa or 'N/A'} → {na or 'N/A'}",
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            alerts.append(alert)

    return alerts


def get_alert_emoji(alert_type: str) -> str:
    emoji_map = {
        "status_change": "🔴",
        "version_change": "🔵",
        "name_change": "🟣",
        "description_change": "📄",
        "icon_change": "🖼",
        "bundle_id_change": "📦",
        "app_id_change": "🆔",
        "error": "🟡",
        "unavailable": "🔴",
        "app_added": "🆕",
        "test": "⚪",
    }
    return emoji_map.get(alert_type, "⚪")


def get_alert_color(alert_type: str) -> str:
    color_map = {
        "status_change": "#ff4757",
        "version_change": "#00d9ff",
        "name_change": "#a55eea",
        "description_change": "#5f27cd",
        "icon_change": "#00b894",
        "bundle_id_change": "#fdcb6e",
        "app_id_change": "#e17055",
        "error": "#ffa502",
        "unavailable": "#ff4757",
        "test": "#747d8c",
    }
    return color_map.get(alert_type, "#747d8c")
