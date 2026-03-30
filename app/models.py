from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class UserRole(enum.Enum):
    """Роли пользователей Telegram"""
    admin = "admin"
    developer = "developer"
    manager = "manager"


class UserStatus(enum.Enum):
    """Статусы пользователей"""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class App(Base):
    """Модель приложения для мониторинга"""

    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    bundle_id = Column(String, unique=True, index=True, nullable=True)
    app_id = Column(String, unique=True, index=True, nullable=True)  # Apple ID (trackId)
    name = Column(String, nullable=True)
    version = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)  # App Store icon URL
    description = Column(Text, nullable=True)  # App description
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_check_at = Column(DateTime, nullable=True)
    next_check_at = Column(DateTime, nullable=True, index=True)
    last_status = Column(String, nullable=True)  # "available", "unavailable", "error"
    last_error = Column(Text, nullable=True)

    # Связи
    check_history = relationship("CheckHistory", back_populates="app", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="app", cascade="all, delete-orphan")


class CheckHistory(Base):
    """История проверок статуса приложения"""

    __tablename__ = "check_history"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    status = Column(String, nullable=False)  # "available", "unavailable", "error"
    version = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    # JSON: снимки до/после, список изменений, тип проверки (scheduled/manual)
    audit_json = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Связи
    app = relationship("App", back_populates="check_history")


class Setting(Base):
    """Модель настроек сервиса"""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)  # например: monitor_interval
    value = Column(Text, nullable=False)  # JSON строка или текст
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Alert(Base):
    """Модель алерта об изменении"""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    alert_type = Column(String, nullable=False)  # status_change, version_change, error, app_added, unavailable
    old_value = Column(Text, nullable=True)  # JSON строка
    new_value = Column(Text, nullable=True)  # JSON строка
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Связи
    app = relationship("App", back_populates="alerts")


class TelegramUser(Base):
    """Модель пользователя Telegram"""

    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)  # Telegram user ID
    username = Column(String, nullable=True)  # @username
    full_name = Column(String, nullable=True)  # Full name
    role = Column(String, default="manager", nullable=False)  # admin/developer/manager
    status = Column(String, default="pending", nullable=False)  # pending/approved/rejected
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey("telegram_users.id"), nullable=True)  # Кто одобрил

    # Связи
    approver = relationship("TelegramUser", remote_side=[id], backref="approved_users")
    notification_settings = relationship("UserNotificationSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserNotificationSettings(Base):
    """Настройки уведомлений пользователя"""

    __tablename__ = "user_notification_settings"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, ForeignKey("telegram_users.id"), unique=True, nullable=False)
    notify_status_change = Column(Boolean, default=True)
    notify_version_change = Column(Boolean, default=True)
    notify_error = Column(Boolean, default=True)
    notify_app_added = Column(Boolean, default=True)
    notify_unavailable = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    user = relationship("TelegramUser", back_populates="notification_settings")
