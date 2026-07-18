"""FVG Service — database operations for Fair Value Gaps."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_

from app.models.fvg import FairValueGap as FVGModel, FVGLifecycleEvent as LifecycleModel
from app.services.fvg.detector import (
    detect_fvgs, apply_lifecycle, FVGConfig, FVG, FVGLifecycleEvent,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class FVGService:
    """Service layer for FVG detection and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def detect_and_store(
        self,
        instrument: str,
        timeframe: str,
        instrument_id: int,
        bars: list,
        config: FVGConfig | None = None,
    ) -> dict:
        """Run FVG detection, apply lifecycle, and store results."""
        if config is None:
            config = FVGConfig()

        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]
        timestamps = [b.timestamp for b in bars]

        # Detect
        fvgs = detect_fvgs(highs, lows, closes, timestamps, instrument, timeframe, config)
        # Apply lifecycle
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, timestamps, config)

        cfg_dict = config.to_dict()
        stored_fvgs = 0
        stored_events = 0

        for fvg in fvgs:
            db_fvg = FVGModel(
                instrument_id=instrument_id,
                timeframe=timeframe,
                direction=fvg.direction,
                status=fvg.status,
                upper_bound=fvg.upper_bound,
                lower_bound=fvg.lower_bound,
                midpoint=fvg.midpoint,
                gap_size=fvg.gap_size,
                gap_size_pct=fvg.gap_size_pct,
                fill_percentage=fvg.fill_percentage,
                creation_bar_index=fvg.creation_bar_index,
                creation_timestamp=fvg.creation_timestamp,
                first_touch_timestamp=fvg.first_touch_timestamp,
                first_touch_bar_index=fvg.first_touch_bar_index,
                mitigation_timestamp=fvg.mitigation_timestamp,
                mitigation_bar_index=fvg.mitigation_bar_index,
                invalidation_timestamp=fvg.invalidation_timestamp,
                invalidation_bar_index=fvg.invalidation_bar_index,
                candle_1_high=fvg.candle_1_high,
                candle_1_low=fvg.candle_1_low,
                candle_2_high=fvg.candle_2_high,
                candle_2_low=fvg.candle_2_low,
                candle_3_high=fvg.candle_3_high,
                candle_3_low=fvg.candle_3_low,
                metadata_json=fvg.metadata,
                config_snapshot=cfg_dict,
            )
            self.session.add(db_fvg)
            await self.session.flush()
            stored_fvgs += 1

            # Store lifecycle events linked to this FVG
            for evt in events:
                if evt.bar_index == fvg.creation_bar_index or (
                    evt.fvg_id is None and _event_belongs_to_fvg(evt, fvg)
                ):
                    db_evt = LifecycleModel(
                        fvg_id=db_fvg.id,
                        instrument_id=instrument_id,
                        timeframe=timeframe,
                        event_type=evt.event_type,
                        bar_index=evt.bar_index,
                        bar_timestamp=evt.timestamp,
                        fill_percentage=evt.fill_percentage,
                        fvg_direction=fvg.direction,
                        fvg_upper=fvg.upper_bound,
                        fvg_lower=fvg.lower_bound,
                        metadata_json=evt.metadata,
                    )
                    self.session.add(db_evt)
                    stored_events += 1

        await self.session.flush()
        logger.info("fvg_detection_complete",
                     instrument=instrument, timeframe=timeframe,
                     fvgs=stored_fvgs, events=stored_events)

        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "fvgs_detected": stored_fvgs,
            "events_stored": stored_events,
            "statuses": _summarize_statuses(fvgs),
        }

    async def get_active_fvgs(
        self,
        instrument_id: int,
        timeframe: str | None = None,
        direction: str | None = None,
        status: str | None = None,
    ) -> list[FVGModel]:
        """Query active (or filtered) FVGs."""
        conditions = [FVGModel.instrument_id == instrument_id]
        if timeframe:
            conditions.append(FVGModel.timeframe == timeframe)
        if direction:
            conditions.append(FVGModel.direction == direction)
        if status:
            conditions.append(FVGModel.status == status)
        else:
            # Default: return non-mitigated/non-invalidated
            conditions.append(
                FVGModel.status.in_(["active", "partially_filled"])
            )

        result = await self.session.execute(
            select(FVGModel)
            .where(and_(*conditions))
            .order_by(FVGModel.creation_timestamp.desc())
            .limit(500)
        )
        return list(result.scalars().all())

    async def get_fvg_events(
        self,
        instrument_id: int,
        timeframe: str | None = None,
        event_type: str | None = None,
        limit: int = 500,
    ) -> list[LifecycleModel]:
        """Query FVG lifecycle events."""
        conditions = [LifecycleModel.instrument_id == instrument_id]
        if timeframe:
            conditions.append(LifecycleModel.timeframe == timeframe)
        if event_type:
            conditions.append(LifecycleModel.event_type == event_type)

        result = await self.session.execute(
            select(LifecycleModel)
            .where(and_(*conditions))
            .order_by(LifecycleModel.bar_timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_fvg_statistics(
        self,
        instrument_id: int,
        timeframe: str | None = None,
    ) -> dict:
        """Get FVG statistics grouped by timeframe and direction."""
        conditions = [FVGModel.instrument_id == instrument_id]
        if timeframe:
            conditions.append(FVGModel.timeframe == timeframe)

        result = await self.session.execute(
            select(FVGModel).where(and_(*conditions))
        )
        fvgs = list(result.scalars().all())

        stats: dict = {}
        for fvg in fvgs:
            tf = fvg.timeframe
            if tf not in stats:
                stats[tf] = {"bullish": 0, "bearish": 0, "mitigated": 0, "active": 0}
            stats[tf][fvg.direction] += 1
            if fvg.status == "mitigated":
                stats[tf]["mitigated"] += 1
            if fvg.status in ("active", "partially_filled"):
                stats[tf]["active"] += 1

        return {"instrument_id": instrument_id, "by_timeframe": stats}


def _event_belongs_to_fvg(evt: FVGLifecycleEvent, fvg: FVG) -> bool:
    """Check if a lifecycle event belongs to a specific FVG."""
    if evt.bar_index < fvg.creation_bar_index:
        return False
    return True


def _summarize_statuses(fvgs: list[FVG]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fvg in fvgs:
        counts[fvg.status] = counts.get(fvg.status, 0) + 1
    return counts
