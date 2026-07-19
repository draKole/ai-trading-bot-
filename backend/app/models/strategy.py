"""Strategy ORM models — Market Bias, Trade Setups, Rules, Evaluations."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketBias(Base):
    """Aggregated directional bias from all engine evidence."""

    __tablename__ = "market_biases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    setup_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    direction: Mapped[str] = mapped_column(String(15), default="neutral")
    strength_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[str] = mapped_column(String(20), default="Very Low")
    trend: Mapped[str] = mapped_column(String(15), default="neutral")
    market_regime: Mapped[str] = mapped_column(String(15), default="ranging")
    session: Mapped[str] = mapped_column(String(20), default="unknown")
    bias_grade: Mapped[str] = mapped_column(String(3), default="F")
    supporting_evidence_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    contradicting_evidence_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class TradeSetup(Base):
    """Advisory trade setup — no execution."""

    __tablename__ = "trade_setups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    setup_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(15), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)

    # Entry
    entry_zone_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_zone_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferred_entry: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Risk reference
    stop_reference: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Targets
    target_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_2: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_3: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Confirmation
    required_confirmation_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Evidence
    bias_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supporting_evidence_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    contradictions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Scoring
    setup_score: Mapped[float] = mapped_column(Float, default=0.0)
    setup_grade: Mapped[str] = mapped_column(String(3), default="F")

    # Metadata
    strategy_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    generated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class StrategyRule(Base):
    """Configurable strategy rule definition."""

    __tablename__ = "strategy_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    direction: Mapped[str] = mapped_column(String(15), default="neutral")
    required_conditions_json: Mapped[list] = mapped_column(JSON, default=list)
    optional_conditions_json: Mapped[list] = mapped_column(JSON, default=list)
    min_score: Mapped[float] = mapped_column(Float, default=60.0)
    group: Mapped[str] = mapped_column(String(50), default="default")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class StrategyEvaluation(Base):
    """Result of evaluating strategy rules against a setup."""

    __tablename__ = "strategy_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    setup_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    direction: Mapped[str] = mapped_column(String(15), default="neutral")
    required_met: Mapped[int] = mapped_column(Integer, default=0)
    required_total: Mapped[int] = mapped_column(Integer, default=0)
    optional_met: Mapped[int] = mapped_column(Integer, default=0)
    optional_total: Mapped[int] = mapped_column(Integer, default=0)
    min_score: Mapped[float] = mapped_column(Float, default=0.0)
    setup_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    group: Mapped[str] = mapped_column(String(50), default="default")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
