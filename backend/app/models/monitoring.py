"""Monitoring ORM models — SystemHealth, Alert, AuditLog, PerformanceMetric."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SystemHealth(Base):
    """Health check record for a system component."""

    __tablename__ = "system_health"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    component: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    detail: Mapped[str] = mapped_column(String(500), default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True,
    )


class Alert(Base):
    """Configurable alert with severity and lifecycle."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True,
    )


class AuditLog(Base):
    """Immutable audit trail entry."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), default="")
    entity_id: Mapped[str] = mapped_column(String(100), default="")
    detail_json: Mapped[str] = mapped_column(String(2000), default="{}")
    operator: Mapped[str] = mapped_column(String(50), default="system")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True,
    )


class PerformanceMetric(Base):
    """Time-series metric data point."""

    __tablename__ = "performance_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    tags_json: Mapped[str] = mapped_column(String(500), default="{}")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True,
    )
