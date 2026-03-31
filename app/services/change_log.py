"""
Единый учёт снимков приложения и списка изменений для истории проверок и алертов.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.models import App

logger = logging.getLogger(__name__)

# Ограничения размера JSON в БД (TEXT)
_SNAPSHOT_TEXT_MAX = 6000
_CHANGE_TEXT_MAX = 1200

FIELD_LABELS = {
    "last_status": "Статус",
    "name": "Название",
    "version": "Версия",
    "store_release_date": "Дата релиза (iTunes)",
    "icon_url": "Иконка (URL)",
    "description": "Описание",
    "bundle_id": "Bundle ID",
    "app_id": "Apple ID",
}


def _norm_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _norm_desc(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def snapshot_from_app(app: App) -> Dict[str, Any]:
    """Снимок полей приложения до/после проверки."""
    return {
        "last_status": app.last_status,
        "name": _norm_str(app.name),
        "version": _norm_str(app.version),
        "store_release_date": _norm_str(getattr(app, "store_release_date", None)),
        "icon_url": _norm_str(app.icon_url),
        "description": _norm_desc(app.description),
        "bundle_id": _norm_str(app.bundle_id),
        "app_id": _norm_str(app.app_id),
    }


def _clip_text(val: Optional[str], max_len: int) -> Optional[str]:
    if val is None:
        return None
    if len(val) <= max_len:
        return val
    return val[:max_len] + "…[усечено]"


def snapshot_for_audit(d: Dict[str, Any]) -> Dict[str, Any]:
    """Копия снимка для JSON-аудита (усечение длинных полей)."""
    out = dict(d)
    if out.get("description"):
        out["description"] = _clip_text(out.get("description"), _SNAPSHOT_TEXT_MAX)
    if out.get("icon_url") and len(out.get("icon_url") or "") > 2000:
        out["icon_url"] = _clip_text(out.get("icon_url"), 2000)
    return out


def list_field_changes(before: Dict[str, Any], after: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Список изменённых полей с подписями (для API и UI)."""
    changes: List[Dict[str, Any]] = []
    for key, label in FIELD_LABELS.items():
        b, a = before.get(key), after.get(key)
        if b != a:
            bo, ao = b, a
            if key == "description":
                bo = _clip_text(b, _CHANGE_TEXT_MAX) if isinstance(b, str) else b
                ao = _clip_text(a, _CHANGE_TEXT_MAX) if isinstance(a, str) else a
            changes.append(
                {
                    "field": key,
                    "label": label,
                    "old": bo,
                    "new": ao,
                }
            )
    return changes


def format_changes_line(before: Dict[str, Any], after: Dict[str, Any]) -> Optional[str]:
    """Краткая строка для поля message в check_history."""
    changes = list_field_changes(before, after)
    if not changes:
        return None
    parts: List[str] = []
    for c in changes:
        f = c["field"]
        if f == "last_status":
            parts.append(f"статус: {c['old']!s}→{c['new']!s}")
        elif f == "version":
            parts.append(f"версия: {c['old']!s}→{c['new']!s}")
        elif f == "store_release_date":
            parts.append("дата релиза iTunes изменена")
        elif f == "name":
            parts.append("название изменено")
        elif f == "icon_url":
            parts.append("иконка изменена")
        elif f == "description":
            parts.append("описание изменено")
        elif f == "bundle_id":
            parts.append("bundle_id изменён")
        elif f == "app_id":
            parts.append("Apple ID изменён")
    return "; ".join(parts)


def build_audit_json(
    before: Dict[str, Any],
    after: Dict[str, Any],
    *,
    check_kind: str,
    api_status: str,
    api_message: Optional[str] = None,
    had_changes: Optional[bool] = None,
) -> Optional[str]:
    """
    Полный JSON для столбца check_history.audit_json.
    check_kind: scheduled | manual
    """
    changes = list_field_changes(before, after)
    if had_changes is None:
        had_changes = len(changes) > 0

    payload = {
        "v": 1,
        "check_kind": check_kind,
        "api": {
            "status": api_status,
            "message": _clip_text(api_message, 4000) if api_message else None,
        },
        "had_changes": had_changes,
        "changes": changes,
        "before": snapshot_for_audit(before),
        "after": snapshot_for_audit(after),
    }
    try:
        return json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.warning("Не удалось сериализовать audit_json: %s", e)
        return None
