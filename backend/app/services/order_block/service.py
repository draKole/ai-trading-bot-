"""Order Block Service — persistence and query layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_

from app.models.order_block import OrderBlock as OBModel, OBLifecycleEvent as LifecycleModel
from app.services.order_block.detector import (
    detect_order_blocks, apply_ob_lifecycle,
    OBConfig, OrderBlock, OBLifecycleEvent,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class OrderBlockService:
    """Service for Order Block detection and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def detect_and_store(
        self,
        instrument: str,
        timeframe: str,
        instrument_id: int,
        bars: list,
        ms_events: list[dict],
        config: OBConfig | None = None,
    ) -> dict:
        """Run OB detection, apply lifecycle, and store."""
        if config is None:
            config = OBConfig()

        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        opens = [b.open for b in bars]
        closes = [b.close for b in bars]
        volumes = [getattr(b, 'volume', 0) for b in bars]
        timestamps = [b.timestamp for b in bars]

        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, timestamps,
            ms_events, instrument, timeframe, config,
        )
        obs, events = apply_ob_lifecycle(obs, highs, lows, closes, timestamps, config)

        cfg_dict = config.to_dict()
        stored_obs = 0
        stored_events = 0

        for ob in obs:
            db_ob = OBModel(
                instrument_id=instrument_id,
                timeframe=timeframe,
                direction=ob.direction,
                status=ob.status,
                upper_bound=ob.upper_bound,
                lower_bound=ob.lower_bound,
                midpoint=ob.midpoint,
                block_size=ob.block_size,
                block_size_pct=ob.block_size_pct,
                mitigation_percentage=ob.mitigation_percentage,
                origin_candle_index=ob.origin_candle_index,
                creation_bar_index=ob.creation_bar_index,
                creation_timestamp=ob.creation_timestamp,
                first_touch_timestamp=ob.first_touch_timestamp,
                first_touch_bar_index=ob.first_touch_bar_index,
                mitigation_timestamp=ob.mitigation_timestamp,
                mitigation_bar_index=ob.mitigation_bar_index,
                invalidation_timestamp=ob.invalidation_timestamp,
                invalidation_bar_index=ob.invalidation_bar_index,
                related_ms_event_id=ob.related_ms_event_id,
                related_liquidity_ids=ob.related_liquidity_ids,
                related_fvg_ids=ob.related_fvg_ids,
                origin_open=ob.origin_open,
                origin_high=ob.origin_high,
                origin_low=ob.origin_low,
                origin_close=ob.origin_close,
                origin_volume=ob.origin_volume,
                metadata_json=ob.metadata,
                config_snapshot=cfg_dict,
            )
            self.session.add(db_ob)
            await self.session.flush()
            stored_obs += 1

            for evt in events:
                if evt.bar_index >= ob.creation_bar_index:
                    db_evt = LifecycleModel(
                        ob_id=db_ob.id,
                        instrument_id=instrument_id,
                        timeframe=timeframe,
                        event_type=evt.event_type,
                        bar_index=evt.bar_index,
                        bar_timestamp=evt.timestamp,
                        mitigation_percentage=evt.mitigation_percentage,
                        ob_direction=ob.direction,
                        ob_upper=ob.upper_bound,
                        ob_lower=ob.lower_bound,
                        metadata_json=evt.metadata,
                    )
                    self.session.add(db_evt)
                    stored_events += 1

        await self.session.flush()
        logger.info("ob_detection_complete",
                     instrument=instrument, timeframe=timeframe,
                     obs=stored_obs, events=stored_events)

        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "obs_detected": stored_obs,
            "events_stored": stored_events,
            "statuses": _summarize_statuses(obs),
        }

    async def get_active_obs(
        self,
        instrument_id: int,
        timeframe: str | None = None,
        direction: str | None = None,
        status: str | None = None,
    ) -> list[OBModel]:
        """Query Order Blocks."""
        conditions = [OBModel.instrument_id == instrument_id]
        if timeframe:
            conditions.append(OBModel.timeframe == timeframe)
        if direction:
            conditions.append(OBModel.direction == direction)
        if status:
            conditions.append(OBModel.status == status)
        else:
            conditions.append(
                OBModel.status.in_(["active", "touched", "partially_mitigated"])
            )

        result = await self.session.execute(
            select(OBModel)
            .where(and_(*conditions))
            .order_by(OBModel.creation_timestamp.desc())
            .limit(500)
        )
        return list(result.scalars().all())

    async def get_ob_events(
        self,
        instrument_id: int,
        timeframe: str | None = None,
        event_type: str | None = None,
        limit: int = 500,
    ) -> list[LifecycleModel]:
        """Query OB lifecycle events."""
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

    async def get_ob_statistics(
        self,
        instrument_id: int,
        timeframe: str | None = None,
    ) -> dict:
        """Get OB statistics grouped by timeframe and direction."""
        conditions = [OBModel.instrument_id == instrument_id]
        if timeframe:
            conditions.append(OBModel.timeframe == timeframe)

        result = await self.session.execute(
            select(OBModel).where(and_(*conditions))
        )
        obs = list(result.scalars().all())

        stats: dict = {}
        for ob in obs:
            tf = ob.timeframe
            if tf not in stats:
                stats[tf] = {"bullish": 0, "bearish": 0, "mitigated": 0, "active": 0}
            stats[tf][ob.direction] += 1
            if ob.status == "mitigated":
                stats[tf]["mitigated"] += 1
            if ob.status in ("active", "touched", "partially_mitigated"):
                stats[tf]["active"] += 1

        return {"instrument_id": instrument_id, "by_timeframe": stats}


def _summarize_statuses(obs: list[OrderBlock]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ob in obs:
        counts[ob.status] = counts.get(ob.status, 0) + 1
    return counts
