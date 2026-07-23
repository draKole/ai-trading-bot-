"""Position Sizing ORM models — Recommendations, Rules, Evaluations."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PositionRecommendation(Base):
    """Advisory position size recommendation."""

    __tablename__ = "position_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True,
    )
    setup_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(15), nullable=False)
    sizing_method: Mapped[str] = mapped_column(String(30), default="fixed_percentage")

    # Quantities
    recommended_contracts: Mapped[int] = mapped_column(Integer, default=0)
    conservative_contracts: Mapped[int] = mapped_column(Integer, default=0)
    max_allowable_contracts: Mapped[int] = mapped_column(Integer, default=0)

    # Dollar values
    dollar_risk_per_contract: Mapped[float] = mapped_column(Float, default=0.0)
    total_dollar_risk: Mapped[float] = mapped_column(Float, default=0.0)
    margin_required: Mapped[float] = mapped_column(Float, default=0.0)
    capital_utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    effective_leverage: Mapped[float] = mapped_column(Float, default=0.0)
    risk_pct_of_account: Mapped[float] = mapped_column(Float, default=0.0)

    # Constraints
    constraint_results_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    all_constraints_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_reasons_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Metadata
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class PositionSizingRule(Base):
    """Configurable position sizing rule definition."""

    __tablename__ = "position_sizing_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    rule_type: Mapped[str] = mapped_column(String(30), default="limit")
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    group: Mapped[str] = mapped_column(String(50), default="default")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class PositionSizingEvaluation(Base):
    """Individual constraint check result."""

    __tablename__ = "position_sizing_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True,
    )
    setup_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(10), default="FAIL")
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
