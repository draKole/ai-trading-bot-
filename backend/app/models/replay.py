"""Historical Replay ORM models — ReplaySession, ReplaySnapshot, ReplayEvent."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReplaySession(Base):
    """A replay session that feeds historical bars through the engine pipeline."""

    __tablename__ = "replay_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default="candle_by_candle",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="idle", index=True,
    )
    bar_count: Mapped[int] = mapped_column(Integer, default=0)
    bar_index: Mapped[int] = mapped_column(Integer, default=0)
    current_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    config_json: Mapped[str | None] = mapped_column(
        String(2000), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow,
    )


class ReplaySnapshot(Base):
    """State snapshot captured after processing each bar during replay."""

    __tablename__ = "replay_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    replay_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("replay_sessions.id"), nullable=False, index=True,
    )
    bar_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    candle_json: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary_json: Mapped[str] = mapped_column(String(5000), nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )


class ReplayEvent(Base):
    """Immutable record of an engine event during replay."""

    __tablename__ = "replay_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    replay_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("replay_sessions.id"), nullable=False, index=True,
    )
    bar_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    engine_source: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_ids_json: Mapped[str] = mapped_column(String(2000), nullable=False, default="[]")
    detail: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
