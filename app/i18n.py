"""
Локализация UI: русский (по умолчанию) и английский.
Язык: cookie «locale» (ru|en), иначе заголовок Accept-Language.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

from starlette.requests import Request

SUPPORTED_LOCALES = frozenset({"ru", "en"})
DEFAULT_LOCALE = "ru"
LOCALE_COOKIE = "locale"


def normalize_locale(lang: Optional[str]) -> str:
    if not lang:
        return DEFAULT_LOCALE
    code = str(lang).strip().lower()[:5]
    if code.startswith("en"):
        return "en"
    if code.startswith("ru"):
        return "ru"
    return DEFAULT_LOCALE


def locale_from_request(request: Request) -> str:
    c = request.cookies.get(LOCALE_COOKIE)
    if c:
        return normalize_locale(c)
    al = (request.headers.get("accept-language") or "").strip()
    if al.lower().startswith("en"):
        return "en"
    return DEFAULT_LOCALE


def safe_redirect_target(request: Request, fallback: str = "/dashboard") -> str:
    ref = request.headers.get("referer")
    if not ref:
        return fallback
    try:
        p = urlparse(ref)
        host = request.url.hostname or ""
        if p.netloc and p.hostname != host:
            return fallback
        path = p.path or fallback
        if not path.startswith("/"):
            return fallback
        return path + (f"?{p.query}" if p.query else "")
    except Exception:
        return fallback


def _merge(*dicts: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for d in dicts:
        out.update(d)
    return out


# Ключи общие для страниц
_COMMON_RU = {
    "nav.dashboard": "Дашборд",
    "nav.alerts": "Алерты",
    "nav.settings": "Настройки",
    "nav.lang": "Язык",
    "lang.ru": "RU",
    "lang.en": "EN",
    "a11y.nav_main": "Основная навигация",
    "common.dash": "—",
    "common.save": "Сохранить",
    "common.error": "Ошибка",
    "common.success_title": "Успешно",
    "status.available": "Доступно",
    "status.unavailable": "Недоступно",
    "status.error": "Ошибка",
    "status.unknown": "Не проверено",
    "field.last_status": "Статус",
    "field.name": "Название",
    "field.version": "Версия",
    "field.icon_url": "Иконка (URL)",
    "field.description": "Описание",
    "field.bundle_id": "Bundle ID",
    "field.app_id": "Apple ID",
}

_COMMON_EN = {
    "nav.dashboard": "Dashboard",
    "nav.alerts": "Alerts",
    "nav.settings": "Settings",
    "nav.lang": "Language",
    "lang.ru": "RU",
    "lang.en": "EN",
    "a11y.nav_main": "Main navigation",
    "common.dash": "—",
    "common.save": "Save",
    "common.error": "Error",
    "common.success_title": "Success",
    "status.available": "Available",
    "status.unavailable": "Unavailable",
    "status.error": "Error",
    "status.unknown": "Not checked",
    "field.last_status": "Status",
    "field.name": "Name",
    "field.version": "Version",
    "field.icon_url": "Icon (URL)",
    "field.description": "Description",
    "field.bundle_id": "Bundle ID",
    "field.app_id": "Apple ID",
}

_DASH_RU = {
    "page.title": "App Store Monitor — Дашборд",
    "page.subtitle": "Мониторинг доступности приложений в реальном времени",
    "stats.total": "Всего приложений",
    "stats.available": "Доступно",
    "stats.unavailable": "Недоступно",
    "stats.errors": "Ошибки",
    "table.title": "Приложения",
    "table.aria": "Список отслеживаемых приложений",
    "col.status": "Статус",
    "col.icon": "Иконка",
    "col.name": "Название",
    "col.bundle": "Bundle ID",
    "col.version": "Версия",
    "col.last_check": "Последняя проверка",
    "col.next_check": "Следующая проверка",
    "col.error": "Ошибка",
    "empty.title": "Нет приложений для мониторинга",
    "empty.hint": "Добавьте первое приложение в настройках или через API",
    "footer.refresh": "Автообновление каждые {secs} секунд · Обновлено:",
    "footer.version": "Версия:",
    "footer.history_hint": "История проверок — в карточке приложения (клик по названию в таблице).",
    "icon.alt": "Иконка приложения {name}",
    "js.icon_alt": "Иконка приложения {name}",
    "bundle.title_copy": "Нажмите, чтобы скопировать",
    "js.no_name": "Без названия",
    "js.history_login": "Войдите, чтобы видеть историю",
    "js.history_unavailable": "История недоступна",
    "js.history_empty": "Записей нет (при включённом фильтре — без изменений карточки)",
    "js.no_message": "Нет сообщения",
    "js.history_load_error": "Не удалось загрузить историю",
    "js.check_kind.manual": "Вручную",
    "js.check_kind.scheduled": "По расписанию",
    "js.no_card_changes": "Изменений в карточке нет",
    "js.api_version": "Версия (ответ API):",
    "js.next_off": "Выкл.",
    "js.copied": "Скопировано",
    "js.check_now": "Проверить сейчас",
    "js.check_pending": "Проверка…",
    "js.check_done": "Готово",
    "js.modal.close": "Закрыть карточку приложения",
    "js.modal.check_aria": "Запустить проверку сейчас",
    "modal.app_default": "Приложение",
    "modal.section.info": "Сведения о приложении",
    "modal.section.history": "История проверок",
    "modal.history_filter": "Только записи с изменениями карточки",
    "modal.loading": "Загрузка…",
    "modal.bundle": "Bundle ID",
    "modal.apple_id": "Apple ID",
    "modal.version": "Версия",
    "modal.status": "Статус",
    "modal.last_check": "Последняя проверка",
    "modal.next_check": "Следующая проверка",
    "modal.last_error": "Последняя ошибка",
    "modal.app_store": "App Store",
    "modal.open_store": "Открыть в App Store →",
}

_DASH_EN = {
    "page.title": "App Store Monitor — Dashboard",
    "page.subtitle": "Real-time App Store availability monitoring",
    "stats.total": "Total apps",
    "stats.available": "Available",
    "stats.unavailable": "Unavailable",
    "stats.errors": "Errors",
    "table.title": "Applications",
    "table.aria": "List of monitored applications",
    "col.status": "Status",
    "col.icon": "Icon",
    "col.name": "Name",
    "col.bundle": "Bundle ID",
    "col.version": "Version",
    "col.last_check": "Last check",
    "col.next_check": "Next check",
    "col.error": "Error",
    "empty.title": "No apps to monitor",
    "empty.hint": "Add your first app in Settings or via the API",
    "footer.refresh": "Auto-refresh every {secs} seconds · Updated:",
    "footer.version": "Version:",
    "footer.history_hint": "Check history is in the app card (click the app name in the table).",
    "icon.alt": "App icon {name}",
    "js.icon_alt": "App icon {name}",
    "bundle.title_copy": "Click to copy",
    "js.no_name": "Untitled",
    "js.history_login": "Sign in to view history",
    "js.history_unavailable": "History unavailable",
    "js.history_empty": "No entries (with filter on — no card changes)",
    "js.no_message": "No message",
    "js.history_load_error": "Failed to load history",
    "js.check_kind.manual": "Manual",
    "js.check_kind.scheduled": "Scheduled",
    "js.no_card_changes": "No card changes",
    "js.api_version": "API version:",
    "js.next_off": "Off",
    "js.copied": "Copied",
    "js.check_now": "Check now",
    "js.check_pending": "Checking…",
    "js.check_done": "Done",
    "js.modal.close": "Close app card",
    "js.modal.check_aria": "Run check now",
    "modal.app_default": "Application",
    "modal.section.info": "App details",
    "modal.section.history": "Check history",
    "modal.history_filter": "Only entries with card changes",
    "modal.loading": "Loading…",
    "modal.bundle": "Bundle ID",
    "modal.apple_id": "Apple ID",
    "modal.version": "Version",
    "modal.status": "Status",
    "modal.last_check": "Last check",
    "modal.next_check": "Next check",
    "modal.last_error": "Last error",
    "modal.app_store": "App Store",
    "modal.open_store": "Open in App Store →",
}

_ALERTS_RU = {
    "page.title": "App Store Monitor — Журнал событий",
    "hero.title": "Журнал событий",
    "page.subtitle": "Алерты и уведомления",
    "stats.total": "Всего",
    "stats.unread": "Непрочитанные",
    "stats.status": "Статус",
    "stats.versions": "Версии",
    "stats.errors": "Ошибки",
    "stats.metadata": "Метаданные",
    "header.events": "События",
    "btn.read_all": "Прочитать все",
    "filter.all": "Все",
    "filter.unread": "Непрочитанные",
    "filter.status": "Статус",
    "filter.versions": "Версии",
    "filter.metadata": "Метаданные",
    "filter.errors": "Ошибки",
    "toolbar.aria": "Фильтры журнала",
    "table.aria": "Журнал алертов",
    "col.type": "Тип",
    "col.app": "Приложение",
    "col.message": "Сообщение",
    "col.time": "Время",
    "col.read_state": "Статус прочтения",
    "col.actions": "Действия",
    "read.read": "Прочитано",
    "read.new": "Новое",
    "empty.filtered": "Нет событий для отображения",
    "empty.loading": "Загрузка…",
    "btn.mark_read_aria": "Отметить как прочитанное",
    "btn.delete_aria": "Удалить событие",
    "type.group_aria": "Тип события",
    "confirm.delete": "Удалить это событие?",
    "type.status_change": "Смена статуса",
    "type.version_change": "Смена версии",
    "type.name_change": "Смена названия",
    "type.description_change": "Смена описания",
    "type.icon_change": "Смена иконки",
    "type.bundle_id_change": "Смена Bundle ID",
    "type.app_id_change": "Смена Apple ID",
    "type.error": "Ошибка",
    "type.app_added": "Новое приложение",
    "type.unavailable": "Недоступно",
    "type.test": "Тест",
}

_ALERTS_EN = {
    "page.title": "App Store Monitor — Event log",
    "hero.title": "Event log",
    "page.subtitle": "Alerts and notifications",
    "stats.total": "Total",
    "stats.unread": "Unread",
    "stats.status": "Status",
    "stats.versions": "Versions",
    "stats.errors": "Errors",
    "stats.metadata": "Metadata",
    "header.events": "Events",
    "btn.read_all": "Mark all read",
    "filter.all": "All",
    "filter.unread": "Unread",
    "filter.status": "Status",
    "filter.versions": "Versions",
    "filter.metadata": "Metadata",
    "filter.errors": "Errors",
    "toolbar.aria": "Log filters",
    "table.aria": "Alert log",
    "col.type": "Type",
    "col.app": "Application",
    "col.message": "Message",
    "col.time": "Time",
    "col.read_state": "Read state",
    "col.actions": "Actions",
    "read.read": "Read",
    "read.new": "New",
    "empty.filtered": "No events to show",
    "empty.loading": "Loading…",
    "btn.mark_read_aria": "Mark as read",
    "btn.delete_aria": "Delete event",
    "type.group_aria": "Event type",
    "confirm.delete": "Delete this event?",
    "type.status_change": "Status change",
    "type.version_change": "Version change",
    "type.name_change": "Name change",
    "type.description_change": "Description change",
    "type.icon_change": "Icon change",
    "type.bundle_id_change": "Bundle ID change",
    "type.app_id_change": "Apple ID change",
    "type.error": "Error",
    "type.app_added": "New app",
    "type.unavailable": "Unavailable",
    "type.test": "Test",
}

_SETTINGS_RU = {
    "page.title": "App Store Monitor — Настройки",
    "hero.title": "Настройки",
    "page.subtitle": "Управление настройками",
    "btn.logout": "Выйти",
    "auth.title": "Авторизация",
    "auth.hint": "Введите данные администратора для доступа к настройкам",
    "auth.login": "Логин",
    "auth.password": "Пароль",
    "auth.submit": "Войти",
    "modal.confirm": "Подтверждение",
    "modal.cancel": "Отмена",
    "modal.confirm_btn": "Подтвердить",
    "section.monitor": "Настройки мониторинга",
    "label.interval": "Интервал проверки (минуты)",
    "label.jitter": "Случайное отклонение (минуты)",
    "section.email": "Email уведомления",
    "label.email_enable": "Включить Email уведомления",
    "label.smtp_host": "SMTP сервер",
    "label.smtp_port": "SMTP порт",
    "label.smtp_user": "SMTP пользователь",
    "label.smtp_password": "SMTP пароль",
    "label.alert_email": "Email для уведомлений",
    "btn.test": "Тест",
    "section.webhook": "Webhook",
    "webhook.hint": "POST JSON на каждый алерт (поля: source, alert_type, app_name, app_identifier, old_value, new_value, created_at). Только http:// или https://.",
    "label.webhook_url": "URL webhook",
    "section.telegram": "Пользователи Telegram",
    "telegram.hint": "Управление пользователями Telegram. Новые пользователи регистрируются через бота @N1Appmon_bot командой /start",
    "btn.refresh_users": "Обновить список",
    "section.apps": "Приложения",
    "placeholder.bundle": "Bundle ID (com.example.app)",
    "placeholder.apple": "Apple ID",
    "btn.add": "Добавить",
    "th.tg_id": "ID",
    "th.username": "Username",
    "th.full_name": "Имя",
    "th.role": "Роль",
    "th.status": "Статус",
    "th.date": "Дата",
    "th.actions": "Действия",
    "apps.bundle": "Bundle ID",
    "apps.apple": "Apple ID",
    "apps.name": "Название",
    "apps.status": "Статус",
    "apps.monitoring": "Мониторинг",
    "apps.actions": "Действия",
    "js.login_apps": "Войдите для просмотра",
    "js.login_tg": "Войдите для просмотра пользователей",
    "js.empty_apps": "Нет приложений",
    "js.empty_users": "Нет пользователей",
    "js.check_title": "Проверить",
    "js.delete_title": "Удалить",
    "js.auth_fail_title": "Ошибка авторизации",
    "js.auth_fail_msg": "Неверный логин или пароль",
    "js.load_fail": "Не удалось загрузить настройки",
    "js.saved_monitor": "Настройки мониторинга сохранены",
    "js.saved_email": "Настройки Email сохранены",
    "js.saved_webhook": "Webhook сохранён",
    "js.enter_id": "Введите Bundle ID или Apple ID",
    "js.add_pending_title": "Добавление",
    "js.add_pending_msg": "Приложение добавляется и проверяется…",
    "js.add_ok": "Приложение добавлено и проверено",
    "js.toggle_fail": "Не удалось изменить статус мониторинга",
    "js.monitor_on": "Мониторинг включён",
    "js.monitor_off": "Мониторинг выключен",
    "js.check_toast_title": "Проверка",
    "js.check_toast_msg": "Приложение проверяется…",
    "js.check_ok": "Приложение проверено",
    "js.check_err": "Ошибка проверки",
    "js.server_err": "Ошибка сервера",
    "js.delete_confirm_title": "Удаление приложения",
    "js.delete_confirm_msg": "Удалить это приложение из мониторинга?",
    "js.delete_ok": "Приложение удалено",
    "js.delete_fail": "Не удалось удалить приложение",
    "js.approve_title": "Одобрить пользователя",
    "js.approve_msg": "Одобрить этого пользователя?",
    "js.approve_ok": "Пользователь одобрен",
    "js.reject_title": "Отклонить пользователя",
    "js.reject_msg": "Отклонить этого пользователя?",
    "js.reject_ok": "Пользователь отклонён",
    "js.role_title": "Изменить роль",
    "js.role_confirm": "Изменить роль на {role}?",
    "js.role_ok": "Роль изменена на {role}",
    "js.users_loaded": "Загружено пользователей: {n}",
    "js.logout_title": "Выход",
    "js.logout_msg": "Вы вышли из системы",
    "js.server_not_json": "Сервер вернул не JSON: {snippet}",
    "js.unknown_err": "Неизвестная ошибка",
    "loader.text": "Загрузка…",
    "modal.confirm_default": "Вы уверены?",
}

_SETTINGS_EN = {
    "page.title": "App Store Monitor — Settings",
    "hero.title": "Settings",
    "page.subtitle": "Configuration",
    "btn.logout": "Log out",
    "auth.title": "Sign in",
    "auth.hint": "Enter admin credentials to access settings",
    "auth.login": "Username",
    "auth.password": "Password",
    "auth.submit": "Sign in",
    "modal.confirm": "Confirm",
    "modal.cancel": "Cancel",
    "modal.confirm_btn": "Confirm",
    "section.monitor": "Monitoring",
    "label.interval": "Check interval (minutes)",
    "label.jitter": "Random jitter (minutes)",
    "section.email": "Email notifications",
    "label.email_enable": "Enable email notifications",
    "label.smtp_host": "SMTP server",
    "label.smtp_port": "SMTP port",
    "label.smtp_user": "SMTP username",
    "label.smtp_password": "SMTP password",
    "label.alert_email": "Notification email",
    "btn.test": "Test",
    "section.webhook": "Webhook",
    "webhook.hint": "POST JSON on each alert (fields: source, alert_type, app_name, app_identifier, old_value, new_value, created_at). Only http:// or https://.",
    "label.webhook_url": "Webhook URL",
    "section.telegram": "Telegram users",
    "telegram.hint": "Manage Telegram users. New users register via bot @N1Appmon_bot with /start",
    "btn.refresh_users": "Refresh list",
    "section.apps": "Applications",
    "placeholder.bundle": "Bundle ID (com.example.app)",
    "placeholder.apple": "Apple ID",
    "btn.add": "Add",
    "th.tg_id": "ID",
    "th.username": "Username",
    "th.full_name": "Name",
    "th.role": "Role",
    "th.status": "Status",
    "th.date": "Date",
    "th.actions": "Actions",
    "apps.bundle": "Bundle ID",
    "apps.apple": "Apple ID",
    "apps.name": "Name",
    "apps.status": "Status",
    "apps.monitoring": "Monitoring",
    "apps.actions": "Actions",
    "js.login_apps": "Please sign in",
    "js.login_tg": "Please sign in to view users",
    "js.empty_apps": "No applications",
    "js.empty_users": "No users",
    "js.check_title": "Check",
    "js.delete_title": "Delete",
    "js.auth_fail_title": "Authentication failed",
    "js.auth_fail_msg": "Invalid username or password",
    "js.load_fail": "Failed to load settings",
    "js.saved_monitor": "Monitoring settings saved",
    "js.saved_email": "Email settings saved",
    "js.saved_webhook": "Webhook saved",
    "js.enter_id": "Enter Bundle ID or Apple ID",
    "js.add_pending_title": "Adding",
    "js.add_pending_msg": "Adding and checking the app…",
    "js.add_ok": "App added and checked",
    "js.toggle_fail": "Could not change monitoring state",
    "js.monitor_on": "Monitoring enabled",
    "js.monitor_off": "Monitoring disabled",
    "js.check_toast_title": "Check",
    "js.check_toast_msg": "Checking app…",
    "js.check_ok": "App checked",
    "js.check_err": "Check failed",
    "js.server_err": "Server error",
    "js.delete_confirm_title": "Remove app",
    "js.delete_confirm_msg": "Remove this app from monitoring?",
    "js.delete_ok": "App removed",
    "js.delete_fail": "Could not remove app",
    "js.approve_title": "Approve user",
    "js.approve_msg": "Approve this user?",
    "js.approve_ok": "User approved",
    "js.reject_title": "Reject user",
    "js.reject_msg": "Reject this user?",
    "js.reject_ok": "User rejected",
    "js.role_title": "Change role",
    "js.role_confirm": "Set role to {role}?",
    "js.role_ok": "Role set to {role}",
    "js.users_loaded": "Loaded users: {n}",
    "js.logout_title": "Signed out",
    "js.logout_msg": "You have been signed out",
    "js.server_not_json": "Server did not return JSON: {snippet}",
    "js.unknown_err": "Unknown error",
    "loader.text": "Loading…",
    "modal.confirm_default": "Are you sure?",
}


def _prefix_keys(prefix: str, d: Dict[str, str]) -> Dict[str, str]:
    return {f"{prefix}.{k}": v for k, v in d.items()}


MESSAGES: Dict[str, Dict[str, str]] = {
    "ru": _merge(
        _COMMON_RU,
        _prefix_keys("dash", _DASH_RU),
        _prefix_keys("alerts", _ALERTS_RU),
        _prefix_keys("settings", _SETTINGS_RU),
    ),
    "en": _merge(
        _COMMON_EN,
        _prefix_keys("dash", _DASH_EN),
        _prefix_keys("alerts", _ALERTS_EN),
        _prefix_keys("settings", _SETTINGS_EN),
    ),
}


def t(locale: str, key: str, **kwargs: Any) -> str:
    loc = normalize_locale(locale)
    bucket = MESSAGES.get(loc) or MESSAGES[DEFAULT_LOCALE]
    text = bucket.get(key)
    if text is None:
        text = MESSAGES[DEFAULT_LOCALE].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def get_status_display(locale: str, status: Optional[str]) -> str:
    key = {
        "available": "status.available",
        "unavailable": "status.unavailable",
        "error": "status.error",
    }.get(status or "", "status.unknown")
    return t(locale, key)


def locale_tag_for_js(locale: str) -> str:
    return "en-US" if normalize_locale(locale) == "en" else "ru-RU"


def dashboard_js_bundle(locale: str) -> Dict[str, str]:
    loc = normalize_locale(locale)
    out: Dict[str, str] = {}
    for k, v in MESSAGES[loc].items():
        if k.startswith("dash.js."):
            out[k.replace("dash.js.", "")] = v
    for fk in (
        "last_status",
        "name",
        "version",
        "icon_url",
        "description",
        "bundle_id",
        "app_id",
    ):
        out[f"field_{fk}"] = t(loc, f"field.{fk}")
    out["status_available"] = t(loc, "status.available")
    out["status_unavailable"] = t(loc, "status.unavailable")
    out["status_error"] = t(loc, "status.error")
    out["status_unknown"] = t(loc, "status.unknown")
    out["cell_empty"] = t(loc, "common.dash")
    return out


def alerts_js_bundle(locale: str) -> Dict[str, str]:
    loc = normalize_locale(locale)
    return {
        "type_status_change": t(loc, "alerts.type.status_change"),
        "type_version_change": t(loc, "alerts.type.version_change"),
        "type_name_change": t(loc, "alerts.type.name_change"),
        "type_description_change": t(loc, "alerts.type.description_change"),
        "type_icon_change": t(loc, "alerts.type.icon_change"),
        "type_bundle_id_change": t(loc, "alerts.type.bundle_id_change"),
        "type_app_id_change": t(loc, "alerts.type.app_id_change"),
        "type_error": t(loc, "alerts.type.error"),
        "type_app_added": t(loc, "alerts.type.app_added"),
        "type_unavailable": t(loc, "alerts.type.unavailable"),
        "type_test": t(loc, "alerts.type.test"),
        "confirm_delete": t(loc, "alerts.confirm.delete"),
        "empty_filtered": t(loc, "alerts.empty.filtered"),
        "empty_loading": t(loc, "alerts.empty.loading"),
        "type_group_aria": t(loc, "alerts.type.group_aria"),
        "read_read": t(loc, "alerts.read.read"),
        "read_new": t(loc, "alerts.read.new"),
        "mark_read_aria": t(loc, "alerts.btn.mark_read_aria"),
        "delete_aria": t(loc, "alerts.btn.delete_aria"),
        "cell_dash": t(loc, "common.dash"),
    }


def settings_js_bundle(locale: str) -> Dict[str, str]:
    loc = normalize_locale(locale)
    out: Dict[str, str] = {}
    for k, v in MESSAGES[loc].items():
        if k.startswith("settings.js."):
            out[k.replace("settings.js.", "")] = v
    out["modal_confirm_default"] = t(loc, "settings.modal.confirm_default")
    out["loader_text"] = t(loc, "settings.loader.text")
    # also status labels for badge
    out["status_available"] = t(loc, "status.available")
    out["status_unavailable"] = t(loc, "status.unavailable")
    out["status_error"] = t(loc, "status.error")
    out["status_unknown"] = t(loc, "status.unknown")
    out["cell_dash"] = t(loc, "common.dash")
    return out
