"""Liquidity ORM models — active levels and historical events."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LiquidityLevel(Base):
    """A detected liquidity level (PDH, session high, equal highs, etc.)."""

    __tablename__ = "liquidity_levels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    level_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    source_bar_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    session: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<LQLevel {self.level_type} @{self.price}>"


class LiquidityEvent(Base):
    """An interaction between price and a liquidity level."""

    __tablename__ = "liquidity_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    level_type: Mapped[str] = mapped_column(String(30), nullable=False)
    level_price: Mapped[float] = mapped_column(Float, nullable=False)
    bar_index: Mapped[int] = mapped_column(Integer, nullable=False)
    bar_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    bar_high: Mapped[float] = mapped_column(Float, nullable=False)
    bar_low: Mapped[float] = mapped_column(Float, nullable=False)
    bar_close: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    distance_pct: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<LQEvent {self.event_type} {self.level_type} @{self.level_price}>"
