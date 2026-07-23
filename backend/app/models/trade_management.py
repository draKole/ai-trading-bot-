"""Trade Management ORM models — Managed Trades, Events, Rules."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ManagedTrade(Base):
    """Stateful representation of a managed trade."""

    __tablename__ = "managed_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    setup_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(15), nullable=False)

    # Entry
    entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    initial_stop: Mapped[float] = mapped_column(Float, default=0.0)
    current_stop: Mapped[float] = mapped_column(Float, default=0.0)
    position_size: Mapped[int] = mapped_column(Integer, default=0)
    position_remaining: Mapped[int] = mapped_column(Integer, default=0)

    # Targets
    target_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_2: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_3: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_1_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    target_2_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    target_3_hit: Mapped[bool] = mapped_column(Boolean, default=False)

    # State
    state: Mapped[str] = mapped_column(String(30), default="pending_entry", index=True)

    # Metrics
    initial_risk_r: Mapped[float] = mapped_column(Float, default=0.0)
    peak_r: Mapped[float] = mapped_column(Float, default=0.0)
    max_adverse_r: Mapped[float] = mapped_column(Float, default=0.0)
    current_r: Mapped[float] = mapped_column(Float, default=0.0)

    # Flags
    breakeven_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    trailing_active: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class TradeEvent(Base):
    """Immutable record of a state transition or management action."""

    __tablename__ = "trade_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    from_state: Mapped[str] = mapped_column(String(30), default="")
    to_state: Mapped[str] = mapped_column(String(30), default="")
    detail: Mapped[str] = mapped_column(String(500), default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float] = mapped_column(Float, default=0.0)
    position_remaining_pct: Mapped[float] = mapped_column(Float, default=100.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class TradeManagementRule(Base):
    """Configurable trade management rule."""

    __tablename__ = "trade_management_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    rule_type: Mapped[str] = mapped_column(String(30), default="threshold")
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    group: Mapped[str] = mapped_column(String(50), default="default")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
