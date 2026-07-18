"""Market Structure Event — ORM model for detected structure events."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketStructureEvent(Base):
    """A detected market structure event (swing, BOS, CHoCH, MSS).

    Stored with full metadata so every event can be traced back
    to the bars and configuration that produced it.
    """

    __tablename__ = "market_structure_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    bar_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price_level: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Parent swing reference — enables tracing structure lineage
    parent_swing_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The bar that confirmed this event (may differ from bar_timestamp for swings)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Configuration snapshot — what params produced this event
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Metadata: bar index, confirmation bar, broken level, etc.
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Schema version for forward compatibility
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<MSEvent {self.event_type} {self.direction or ''} "
            f"@{self.price_level} {self.bar_timestamp:%Y-%m-%d %H:%M}>"
        )
