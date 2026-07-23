"""Risk ORM models — Risk Reports, Rules, and Evaluations."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RiskReport(Base):
    """Complete risk evaluation report for a trade setup."""

    __tablename__ = "risk_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    setup_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(15), nullable=False)

    # Scores
    overall_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_classification: Mapped[str] = mapped_column(
        String(15), default="Extreme", index=True,
    )

    # Key metrics
    reward_risk_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    stop_distance_pct: Mapped[float] = mapped_column(Float, default=0.0)
    mfe_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    volatility_pct: Mapped[float] = mapped_column(Float, default=0.0)
    setup_stability_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Validation (full summary as JSON)
    validation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Evidence
    supporting_evidence_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    contradicting_evidence_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    failure_reasons_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Config snapshot
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class RiskRule(Base):
    """Configurable risk validation rule definition."""

    __tablename__ = "risk_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    rule_type: Mapped[str] = mapped_column(String(30), default="threshold")
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    warn_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    operator: Mapped[str] = mapped_column(String(10), default="gte")
    field: Mapped[str] = mapped_column(String(50), default="")
    group: Mapped[str] = mapped_column(String(50), default="default")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class RiskEvaluation(Base):
    """Individual validation check result."""

    __tablename__ = "risk_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    setup_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    result: Mapped[str] = mapped_column(String(10), default="FAIL")
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
