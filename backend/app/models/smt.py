"""SMT ORM models — divergence events and pair configurations."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SMTEvent(Base):
    """A detected SMT Divergence between two correlated instruments."""

    __tablename__ = "smt_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    primary_instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    secondary_instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # Primary swing
    primary_swing_type: Mapped[str] = mapped_column(String(15), nullable=False)
    primary_swing_price: Mapped[float] = mapped_column(Float, nullable=False)
    primary_swing_bar_index: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_swing_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    primary_prior_swing_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    primary_ms_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Secondary swing
    secondary_swing_type: Mapped[str] = mapped_column(String(15), nullable=False)
    secondary_swing_price: Mapped[float] = mapped_column(Float, nullable=False)
    secondary_swing_bar_index: Mapped[int] = mapped_column(Integer, nullable=False)
    secondary_swing_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    secondary_prior_swing_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    secondary_ms_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Divergence metrics
    divergence_pct: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp_delta_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    # Detection metadata
    detection_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    detection_bar_index: Mapped[int] = mapped_column(Integer, default=0)

    # Related entities
    related_liquidity_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    related_fvg_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    related_ob_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class SMTPairConfig(Base):
    """Stored configuration for an instrument pair."""

    __tablename__ = "smt_pair_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    primary_instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    secondary_instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timestamp_tolerance_seconds: Mapped[float] = mapped_column(Float, default=300.0)
    min_divergence_pct: Mapped[float] = mapped_column(Float, default=0.05)
    enabled_timeframes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
