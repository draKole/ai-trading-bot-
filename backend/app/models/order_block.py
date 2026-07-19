"""Order Block ORM models — active blocks, lifecycle events."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderBlock(Base):
    """A detected Order Block traceable to Market Structure."""

    __tablename__ = "order_blocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(25), nullable=False, index=True)
    upper_bound: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[float] = mapped_column(Float, nullable=False)
    midpoint: Mapped[float] = mapped_column(Float, nullable=False)
    block_size: Mapped[float] = mapped_column(Float, nullable=False)
    block_size_pct: Mapped[float] = mapped_column(Float, nullable=False)
    mitigation_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    origin_candle_index: Mapped[int] = mapped_column(Integer, nullable=False)
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

    # Related entities
    related_ms_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    related_liquidity_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    related_fvg_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Origin candle
    origin_open: Mapped[float] = mapped_column(Float, default=0.0)
    origin_high: Mapped[float] = mapped_column(Float, default=0.0)
    origin_low: Mapped[float] = mapped_column(Float, default=0.0)
    origin_close: Mapped[float] = mapped_column(Float, default=0.0)
    origin_volume: Mapped[float] = mapped_column(Float, default=0.0)

    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class OBLifecycleEvent(Base):
    """A lifecycle state transition for an Order Block."""

    __tablename__ = "ob_lifecycle_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ob_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    instrument_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    event_type: Mapped[str] = mapped_column(String(25), nullable=False, index=True)
    bar_index: Mapped[int] = mapped_column(Integer, nullable=False)
    bar_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    mitigation_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    ob_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ob_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    ob_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
