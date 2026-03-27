from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class App(Base):
    """Модель приложения для мониторинга"""

    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    bundle_id = Column(String, unique=True, index=True, nullable=True)
    app_id = Column(String, unique=True, index=True, nullable=True)  # Apple ID (trackId)
    name = Column(String, nullable=True)
    version = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_check_at = Column(DateTime, nullable=True)
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
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Связи
    app = relationship("App", back_populates="check_history")


class APIKey(Base):
    """Модель API ключа для доступа к сервису"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    request_count = Column(Integer, default=0)
    hourly_request_count = Column(Integer, default=0)
    hourly_reset_at = Column(DateTime, nullable=True)


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
    alert_type = Column(String, nullable=False)  # status_change, version_change, error
    old_value = Column(Text, nullable=True)  # JSON строка
    new_value = Column(Text, nullable=True)  # JSON строка
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Связи
    app = relationship("App", back_populates="alerts")
