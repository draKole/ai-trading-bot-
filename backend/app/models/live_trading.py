"""Live Trading ORM models — Session, Order, Execution, ConnectionLog."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LiveTradingSession(Base):
    """A live trading session connected to a broker."""

    __tablename__ = "live_trading_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True,
    )
    broker: Mapped[str] = mapped_column(String(30), nullable=False, default="tradovate")
    connection_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="disconnected",
    )
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    buying_power: Mapped[float] = mapped_column(Float, default=0.0)
    initial_balance: Mapped[float] = mapped_column(Float, default=100_000.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    config_json: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class LiveOrder(Base):
    """A broker-routed order in a live session."""

    __tablename__ = "live_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("live_trading_sessions.id"), nullable=False, index=True,
    )
    broker_order_id: Mapped[str] = mapped_column(String(50), default="")
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True,
    )
    filled_qty: Mapped[int] = mapped_column(Integer, default=0)
    avg_fill_price: Mapped[float] = mapped_column(Float, default=0.0)
    rejected_reason: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class LiveExecution(Base):
    """Immutable fill record from a broker."""

    __tablename__ = "live_executions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("live_trading_sessions.id"), nullable=False, index=True,
    )
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("live_orders.id"), nullable=False, index=True,
    )
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class BrokerConnectionLog(Base):
    """Connection event log for audit trail."""

    __tablename__ = "broker_connection_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("live_trading_sessions.id"), nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str] = mapped_column(String(500), default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
