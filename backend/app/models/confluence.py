"""Confluence ORM models — snapshots, rule results, rule definitions."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConfluenceSnapshot(Base):
    """A unified market state snapshot combining all engine outputs."""

    __tablename__ = "confluence_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )

    # Trend
    trend: Mapped[str] = mapped_column(String(15), default="neutral")
    trend_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Market Structure counts
    ms_event_count: Mapped[int] = mapped_column(Integer, default=0)
    ms_bullish_count: Mapped[int] = mapped_column(Integer, default=0)
    ms_bearish_count: Mapped[int] = mapped_column(Integer, default=0)
    swing_direction: Mapped[str] = mapped_column(String(15), default="neutral")
    latest_bos_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latest_choch_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Liquidity
    liquidity_level_count: Mapped[int] = mapped_column(Integer, default=0)
    active_sweeps_count: Mapped[int] = mapped_column(Integer, default=0)
    active_sweeps_bullish: Mapped[int] = mapped_column(Integer, default=0)
    active_sweeps_bearish: Mapped[int] = mapped_column(Integer, default=0)

    # FVGs
    fvg_active_count: Mapped[int] = mapped_column(Integer, default=0)
    fvg_bullish_count: Mapped[int] = mapped_column(Integer, default=0)
    fvg_bearish_count: Mapped[int] = mapped_column(Integer, default=0)
    fvg_mitigated_count: Mapped[int] = mapped_column(Integer, default=0)

    # Order Blocks
    ob_active_count: Mapped[int] = mapped_column(Integer, default=0)
    ob_bullish_count: Mapped[int] = mapped_column(Integer, default=0)
    ob_bearish_count: Mapped[int] = mapped_column(Integer, default=0)
    ob_mitigated_count: Mapped[int] = mapped_column(Integer, default=0)

    # SMT
    smt_active_count: Mapped[int] = mapped_column(Integer, default=0)
    smt_bullish_count: Mapped[int] = mapped_column(Integer, default=0)
    smt_bearish_count: Mapped[int] = mapped_column(Integer, default=0)

    # Session
    session: Mapped[str] = mapped_column(String(20), default="unknown")
    session_aligned: Mapped[bool] = mapped_column(Boolean, default=False)

    # Aggregate
    bullish_signals: Mapped[float] = mapped_column(Float, default=0.0)
    bearish_signals: Mapped[float] = mapped_column(Float, default=0.0)
    neutral_signals: Mapped[int] = mapped_column(Integer, default=0)
    total_signals: Mapped[float] = mapped_column(Float, default=0.0)
    agreement_ratio: Mapped[float] = mapped_column(Float, default=0.0)

    # Metadata
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class ConfluenceRuleResult(Base):
    """Result of evaluating a single rule against a snapshot."""

    __tablename__ = "confluence_rule_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    matched: Mapped[bool] = mapped_column(Boolean, default=False)
    direction: Mapped[str] = mapped_column(String(15), default="neutral")
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    total_conditions: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    matched_conditions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class ConfluenceRule(Base):
    """Stored rule definition."""

    __tablename__ = "confluence_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    conditions_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    operator: Mapped[str] = mapped_column(String(20), default="all")
    min_matches: Mapped[int] = mapped_column(Integer, default=1)
    group: Mapped[str] = mapped_column(String(50), default="default")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    direction: Mapped[str] = mapped_column(String(15), default="neutral")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
