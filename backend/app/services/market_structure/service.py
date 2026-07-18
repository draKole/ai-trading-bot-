"""Market Structure Service — database operations for structure events."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.models.market_structure import MarketStructureEvent as MSEvent
from app.services.market_structure.engine import MarketStructureEngine
from app.services.market_structure.config import MarketStructureConfig
from app.services.market_structure.structure_analyzer import (
    StructureEvent,
    StructureEventType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class MarketStructureService:
    """Service layer for market structure detection and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def detect_and_store(
        self,
        instrument: str,
        timeframe: str,
        instrument_id: int,
        bars: list,
        config: MarketStructureConfig | None = None,
    ) -> dict:
        """Run detection and store events in the database.

        Returns a summary dict.
        """
        engine = MarketStructureEngine(config)
        events = engine.analyze_from_ohlcv(bars, instrument, timeframe)

        if not events:
            return {"instrument": instrument, "timeframe": timeframe, "events_stored": 0}

        # Store events
        stored = 0
        for evt in events:
            db_event = MSEvent(
                instrument_id=instrument_id,
                timeframe=timeframe,
                bar_timestamp=evt.timestamp,
                event_type=evt.event_type.value,
                price_level=evt.price_level,
                direction=evt.direction,
                config_snapshot=(config or MarketStructureConfig()).to_dict(),
                metadata_json=evt.metadata,
                schema_version="1.0",
            )
            self.session.add(db_event)
            stored += 1

        await self.session.flush()

        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "events_stored": stored,
            "event_types": _summarize_types(events),
        }

    async def get_events(
        self,
        instrument_id: int,
        timeframe: str | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[MSEvent]:
        """Query stored structure events."""
        conditions = [MSEvent.instrument_id == instrument_id]
        if timeframe:
            conditions.append(MSEvent.timeframe == timeframe)
        if event_type:
            conditions.append(MSEvent.event_type == event_type)
        if start:
            conditions.append(MSEvent.bar_timestamp >= start)
        if end:
            conditions.append(MSEvent.bar_timestamp <= end)

        result = await self.session.execute(
            select(MSEvent)
            .where(*conditions)
            .order_by(MSEvent.bar_timestamp.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_structure(
        self,
        instrument_id: int,
        timeframe: str,
    ) -> dict:
        """Get the latest market structure summary."""
        # Latest swing high
        sh = await self.session.execute(
            select(MSEvent)
            .where(
                MSEvent.instrument_id == instrument_id,
                MSEvent.timeframe == timeframe,
                MSEvent.event_type.in_([
                    "swing_high", "higher_high", "lower_high",
                ]),
            )
            .order_by(MSEvent.bar_timestamp.desc())
            .limit(1)
        )
        latest_high = sh.scalar_one_or_none()

        # Latest swing low
        sl = await self.session.execute(
            select(MSEvent)
            .where(
                MSEvent.instrument_id == instrument_id,
                MSEvent.timeframe == timeframe,
                MSEvent.event_type.in_([
                    "swing_low", "higher_low", "lower_low",
                ]),
            )
            .order_by(MSEvent.bar_timestamp.desc())
            .limit(1)
        )
        latest_low = sl.scalar_one_or_none()

        # Latest BOS/CHoCH/MSS
        bos = await self.session.execute(
            select(MSEvent)
            .where(
                MSEvent.instrument_id == instrument_id,
                MSEvent.timeframe == timeframe,
                MSEvent.event_type.in_(["bos", "choch", "mss"]),
            )
            .order_by(MSEvent.bar_timestamp.desc())
            .limit(1)
        )
        latest_break = bos.scalar_one_or_none()

        return {
            "latest_swing_high": _event_to_dict(latest_high),
            "latest_swing_low": _event_to_dict(latest_low),
            "latest_break": _event_to_dict(latest_break),
        }


def _summarize_types(events: list[StructureEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in events:
        key = e.event_type.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _event_to_dict(evt: MSEvent | None) -> dict | None:
    if evt is None:
        return None
    return {
        "event_type": evt.event_type,
        "price_level": evt.price_level,
        "direction": evt.direction,
        "timestamp": evt.bar_timestamp.isoformat(),
    }
