"""Audit Log ORM model — immutable record of all trading events."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TradingAuditLog(Base):
    """Immutable audit trail of all orders, fills, cancels, and modifications.

    Every order lifecycle event is recorded. Records are append-only —
    no updates or deletes allowed through the API.
    """

    __tablename__ = "trading_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True,
    )  # order_placed, order_filled, order_cancelled, order_modified, kill_switch, mode_switch
    client_order_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
    )
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument: Mapped[str | None] = mapped_column(String(20), nullable=True)
    side: Mapped[str | None] = mapped_column(String(10), nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mode: Mapped[str | None] = mapped_column(
        String(10), nullable=True, index=True,
    )  # paper or live
    metadata_json: Mapped[str | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True,
    )
