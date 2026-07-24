"""Backtesting ORM models — BacktestRun, BacktestTrade, BacktestMetrics."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BacktestRun(Base):
    """A single backtesting run — configuration and results."""

    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    total_bars: Mapped[int] = mapped_column(Integer, default=0)
    config_json: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    metrics_json: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    equity_curve_json: Mapped[str | None] = mapped_column(String(20000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class BacktestTrade(Base):
    """A completed trade recorded during backtesting."""

    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtest_runs.id"), nullable=False, index=True,
    )
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_price: Mapped[float] = mapped_column(Float, default=0.0)
    risk: Mapped[float] = mapped_column(Float, default=0.0)
    r_multiple: Mapped[float] = mapped_column(Float, default=0.0)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    exit_reason: Mapped[str] = mapped_column(String(50), default="")
    strategy_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class BacktestMetrics(Base):
    """Aggregated performance metrics for a backtest run."""

    __tablename__ = "backtest_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtest_runs.id"), nullable=False, unique=True,
    )

    # P&L
    net_profit: Mapped[float] = mapped_column(Float, default=0.0)
    gross_profit: Mapped[float] = mapped_column(Float, default=0.0)
    gross_loss: Mapped[float] = mapped_column(Float, default=0.0)

    # Trade counts
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)
    breakeven_trades: Mapped[int] = mapped_column(Integer, default=0)

    # Rates
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    loss_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # Ratios
    profit_factor: Mapped[float] = mapped_column(Float, default=0.0)

    # Averages
    average_win: Mapped[float] = mapped_column(Float, default=0.0)
    average_loss: Mapped[float] = mapped_column(Float, default=0.0)
    average_r: Mapped[float] = mapped_column(Float, default=0.0)

    # Expectancy
    expectancy: Mapped[float] = mapped_column(Float, default=0.0)

    # Drawdown
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # Streaks
    max_consecutive_wins: Mapped[int] = mapped_column(Integer, default=0)
    max_consecutive_losses: Mapped[int] = mapped_column(Integer, default=0)

    # Duration
    average_trade_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    # Directional
    long_trades: Mapped[int] = mapped_column(Integer, default=0)
    long_wins: Mapped[int] = mapped_column(Integer, default=0)
    long_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    short_trades: Mapped[int] = mapped_column(Integer, default=0)
    short_wins: Mapped[int] = mapped_column(Integer, default=0)
    short_pnl: Mapped[float] = mapped_column(Float, default=0.0)

    # Extremes
    largest_winner: Mapped[float] = mapped_column(Float, default=0.0)
    largest_loser: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
