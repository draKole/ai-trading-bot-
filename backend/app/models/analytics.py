"""Analytics ORM models — AnalyticsReport and StrategyComparison."""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnalyticsReport(Base):
    """Cached analytics report for a backtest run."""

    __tablename__ = "analytics_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtest_runs.id"), nullable=False, index=True,
    )
    report_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="full",
    )
    metrics_json: Mapped[str] = mapped_column(String(10000), nullable=False, default="{}")
    charts_json: Mapped[str] = mapped_column(String(20000), nullable=False, default="{}")
    summary_json: Mapped[str] = mapped_column(String(5000), nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class StrategyComparison(Base):
    """Comparison of multiple backtest runs."""

    __tablename__ = "strategy_comparisons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_ids: Mapped[str] = mapped_column(
        String(2000), nullable=False, default="[]",
    )
    comparison_json: Mapped[str] = mapped_column(
        String(20000), nullable=False, default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
