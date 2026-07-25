"""Portfolio ORM models — Portfolio, PortfolioAccount, AllocationRule, PortfolioPosition, PortfolioStatistic."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Portfolio(Base):
    """A managed portfolio grouping multiple accounts."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    total_capital: Mapped[float] = mapped_column(Float, default=0.0)
    allocated_capital: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    config_json: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PortfolioAccount(Base):
    """An account within a portfolio."""

    __tablename__ = "portfolio_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id"), nullable=False, index=True,
    )
    account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), default="paper")
    name: Mapped[str] = mapped_column(String(100), default="")
    allocation_pct: Mapped[float] = mapped_column(Float, default=0.0)
    allocation_method: Mapped[str] = mapped_column(String(20), default="equal")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AllocationRule(Base):
    """Capital allocation rule."""

    __tablename__ = "allocation_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id"), nullable=False, index=True,
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="equal")
    parameter: Mapped[float] = mapped_column(Float, default=0.0)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PortfolioPosition(Base):
    """Aggregated position across all accounts in a portfolio."""

    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id"), nullable=False, index=True,
    )
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    total_quantity: Mapped[int] = mapped_column(Integer, default=0)
    avg_entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PortfolioStatistic(Base):
    """Portfolio-level performance statistic."""

    __tablename__ = "portfolio_statistics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id"), nullable=False, index=True,
    )
    total_equity: Mapped[float] = mapped_column(Float, default=0.0)
    daily_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    exposure: Mapped[float] = mapped_column(Float, default=0.0)
    capital_utilization: Mapped[float] = mapped_column(Float, default=0.0)
    account_count: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True,
    )
