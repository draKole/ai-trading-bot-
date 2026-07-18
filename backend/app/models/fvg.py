"""FVG ORM models — active gaps, lifecycle events, and history."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FairValueGap(Base):
    """A detected Fair Value Gap with full lifecycle tracking."""

    __tablename__ = "fair_value_gaps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    upper_bound: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[float] = mapped_column(Float, nullable=False)
    midpoint: Mapped[float] = mapped_column(Float, nullable=False)
    gap_size: Mapped[float] = mapped_column(Float, nullable=False)
    gap_size_pct: Mapped[float] = mapped_column(Float, nullable=False)
    fill_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    creation_bar_index: Mapped[int] = mapped_column(Integer, nullable=False)
    creation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    first_touch_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    first_touch_bar_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mitigation_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    mitigation_bar_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    invalidation_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    invalidation_bar_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Candle data for audit
    candle_1_high: Mapped[float] = mapped_column(Float, default=0.0)
    candle_1_low: Mapped[float] = mapped_column(Float, default=0.0)
    candle_2_high: Mapped[float] = mapped_column(Float, default=0.0)
    candle_2_low: Mapped[float] = mapped_column(Float, default=0.0)
    candle_3_high: Mapped[float] = mapped_column(Float, default=0.0)
    candle_3_low: Mapped[float] = mapped_column(Float, default=0.0)

    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class FVGLifecycleEvent(Base):
    """A lifecycle state transition for an FVG."""

    __tablename__ = "fvg_lifecycle_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fvg_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    instrument_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    bar_index: Mapped[int] = mapped_column(Integer, nullable=False)
    bar_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    fill_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    fvg_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fvg_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    fvg_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
