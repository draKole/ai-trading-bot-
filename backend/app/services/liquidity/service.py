"""Liquidity Service — database operations for liquidity levels and events."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_

from app.models.liquidity import LiquidityLevel as LQLevel, LiquidityEvent as LQEvent
from app.services.liquidity.engine import (
    LiquidityEngine, LiquidityConfig, LiquidityLevel, LiquidityEvent,
    LiquidityEventType,
)
from app.services.market_structure.swing_detector import detect_swings, SwingPoint

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class LiquidityService:
    """Service layer for liquidity detection and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def detect_and_store(
        self,
        instrument: str,
        timeframe: str,
        instrument_id: int,
        bars: list,
        config: LiquidityConfig | None = None,
    ) -> dict:
        """Run liquidity detection on bars and store levels/events."""
        engine = LiquidityEngine(config)

        # Detect swings first (needed for equal highs/lows, swing liquidity)
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        timestamps = [b.timestamp for b in bars]
        cfg = config or LiquidityConfig()
        swings = detect_swings(
            highs, lows, timestamps,
            lookback=5,
            confirmation_bars=0,
            min_distance_bars=3,
        )

        # Detect levels
        levels = engine.detect_levels(bars, swings, instrument)
        # Detect events
        events = engine.detect_events(levels, bars)

        # Store levels
        level_count = 0
        for lvl in levels:
            db_level = LQLevel(
                instrument_id=instrument_id,
                timeframe=timeframe,
                level_type=lvl.level_type.value,
                price=lvl.price,
                source_bar_index=lvl.source_bar_index,
                source_timestamp=lvl.source_timestamp,
                session=lvl.session.value if lvl.session else None,
                is_active=True,
                metadata_json=lvl.metadata,
                config_snapshot=cfg.to_dict(),
            )
            self.session.add(db_level)
            level_count += 1

        # Store events
        event_count = 0
        for evt in events:
            db_event = LQEvent(
                instrument_id=instrument_id,
                timeframe=timeframe,
                event_type=evt.event_type.value,
                level_type=evt.level.level_type.value,
                level_price=evt.level.price,
                bar_index=evt.bar_index,
                bar_timestamp=evt.timestamp,
                bar_high=evt.bar_high,
                bar_low=evt.bar_low,
                bar_close=evt.bar_close,
                direction=evt.direction,
                distance_pct=evt.distance_pct,
                metadata_json=evt.metadata,
                config_snapshot=cfg.to_dict(),
            )
            self.session.add(db_event)
            event_count += 1

        await self.session.flush()

        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "levels_detected": level_count,
            "events_detected": event_count,
        }

    async def get_active_levels(
        self,
        instrument_id: int,
        timeframe: str | None = None,
        level_type: str | None = None,
    ) -> list[LQLevel]:
        """Query active liquidity levels."""
        conditions = [
            LQLevel.instrument_id == instrument_id,
            LQLevel.is_active == True,
        ]
        if timeframe:
            conditions.append(LQLevel.timeframe == timeframe)
        if level_type:
            conditions.append(LQLevel.level_type == level_type)

        result = await self.session.execute(
            select(LQLevel).where(and_(*conditions)).order_by(LQLevel.price.desc())
        )
        return list(result.scalars().all())

    async def get_events(
        self,
        instrument_id: int,
        timeframe: str | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[LQEvent]:
        """Query liquidity events."""
        conditions = [LQEvent.instrument_id == instrument_id]
        if timeframe:
            conditions.append(LQEvent.timeframe == timeframe)
        if event_type:
            conditions.append(LQEvent.event_type == event_type)
        if start:
            conditions.append(LQEvent.bar_timestamp >= start)
        if end:
            conditions.append(LQEvent.bar_timestamp <= end)

        result = await self.session.execute(
            select(LQEvent)
            .where(and_(*conditions))
            .order_by(LQEvent.bar_timestamp.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_sweeps(
        self,
        instrument_id: int,
        timeframe: str | None = None,
        limit: int = 200,
    ) -> list[LQEvent]:
        """Query sweep events specifically."""
        return await self.get_events(
            instrument_id, timeframe,
            event_type=LiquidityEventType.SWEPT.value,
            limit=limit,
        )

    async def get_session_status(
        self,
        instrument_id: int,
        session: str,
    ) -> dict:
        """Get current session's liquidity status."""
        result = await self.session.execute(
            select(LQLevel)
            .where(
                LQLevel.instrument_id == instrument_id,
                LQLevel.is_active == True,
                LQLevel.session == session,
            )
            .order_by(LQLevel.price.desc())
        )
        levels = list(result.scalars().all())
        return {
            "session": session,
            "active_levels": len(levels),
            "levels": [
                {
                    "type": l.level_type,
                    "price": l.price,
                    "timestamp": l.source_timestamp.isoformat(),
                }
                for l in levels
            ],
        }

    async def deactivate_level(self, level_id: int) -> None:
        """Mark a liquidity level as inactive."""
        result = await self.session.execute(
            select(LQLevel).where(LQLevel.id == level_id)
        )
        level = result.scalar_one_or_none()
        if level:
            level.is_active = False
            await self.session.flush()
