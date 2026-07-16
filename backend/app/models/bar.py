"""OHLCV Bar model — TimescaleDB hypertable for market data."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Bar(Base):
    """Normalized OHLCV bar — the canonical market data unit.

    Stored in a TimescaleDB hypertable partitioned by time.
    Unique constraint on (instrument_id, timeframe, timestamp, provider)
    prevents duplicates.
    """

    __tablename__ = "bars"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timeframe", "timestamp", "provider",
            name="uq_bar_instrument_tf_ts_provider",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<Bar {self.instrument_id} {self.timeframe} "
            f"{self.timestamp:%Y-%m-%d %H:%M} O:{self.open} H:{self.high} "
            f"L:{self.low} C:{self.close} V:{self.volume}>"
        )
