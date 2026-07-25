"""Dashboard ORM models — DashboardSnapshot, DashboardPreference, DashboardLayout."""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DashboardSnapshot(Base):
    __tablename__ = "dashboard_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_type: Mapped[str] = mapped_column(String(50), nullable=False, default="full", index=True)
    data_json: Mapped[str | None] = mapped_column(String(10000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DashboardPreference(Base):
    __tablename__ = "dashboard_preferences"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True, default=0)
    preference_key: Mapped[str] = mapped_column(String(100), nullable=False)
    preference_value: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DashboardLayout(Base):
    __tablename__ = "dashboard_layouts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True, default=0)
    layout_name: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    widgets_json: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
