"""SMT Service — persistence and query layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_

from app.models.smt import SMTEvent as SMTModel, SMTPairConfig as PairConfigModel
from app.services.smt.detector import detect_smt_divergence, SMTConfig, SMTEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class SMTService:
    """Service for SMT Divergence detection and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def detect_and_store(
        self,
        primary_instrument: str,
        secondary_instrument: str,
        timeframe: str,
        primary_swings: list[dict],
        secondary_swings: list[dict],
        config: SMTConfig | None = None,
    ) -> dict:
        """Run SMT detection and store results."""
        if config is None:
            config = SMTConfig()

        events = detect_smt_divergence(
            primary_swings=primary_swings,
            secondary_swings=secondary_swings,
            primary_instrument=primary_instrument,
            secondary_instrument=secondary_instrument,
            timeframe=timeframe,
            config=config,
        )

        cfg_dict = config.to_dict()
        stored = 0

        for evt in events:
            db_evt = SMTModel(
                primary_instrument=evt.primary_instrument,
                secondary_instrument=evt.secondary_instrument,
                timeframe=evt.timeframe,
                direction=evt.direction,
                primary_swing_type=evt.primary_swing_type,
                primary_swing_price=evt.primary_swing_price,
                primary_swing_bar_index=evt.primary_swing_bar_index,
                primary_swing_timestamp=evt.primary_swing_timestamp,
                primary_prior_swing_price=evt.primary_prior_swing_price,
                primary_ms_event_id=evt.primary_ms_event_id,
                secondary_swing_type=evt.secondary_swing_type,
                secondary_swing_price=evt.secondary_swing_price,
                secondary_swing_bar_index=evt.secondary_swing_bar_index,
                secondary_swing_timestamp=evt.secondary_swing_timestamp,
                secondary_prior_swing_price=evt.secondary_prior_swing_price,
                secondary_ms_event_id=evt.secondary_ms_event_id,
                divergence_pct=evt.divergence_pct,
                timestamp_delta_seconds=evt.timestamp_delta_seconds,
                detection_timestamp=evt.detection_timestamp,
                detection_bar_index=evt.detection_bar_index,
                related_liquidity_ids=evt.related_liquidity_ids,
                related_fvg_ids=evt.related_fvg_ids,
                related_ob_ids=evt.related_ob_ids,
                metadata_json=evt.metadata,
                config_snapshot=cfg_dict,
            )
            self.session.add(db_evt)
            stored += 1

        await self.session.flush()
        logger.info("smt_detection_complete",
                     pair=f"{primary_instrument}/{secondary_instrument}",
                     timeframe=timeframe, events=stored)

        return {
            "pair": f"{primary_instrument}/{secondary_instrument}",
            "timeframe": timeframe,
            "events_detected": stored,
            "directions": _summarize_directions(events),
        }

    async def get_events(
        self,
        primary_instrument: str | None = None,
        secondary_instrument: str | None = None,
        timeframe: str | None = None,
        direction: str | None = None,
        limit: int = 500,
    ) -> list[SMTModel]:
        """Query SMT events with optional filters."""
        conditions = []
        if primary_instrument:
            conditions.append(SMTModel.primary_instrument == primary_instrument.upper())
        if secondary_instrument:
            conditions.append(SMTModel.secondary_instrument == secondary_instrument.upper())
        if timeframe:
            conditions.append(SMTModel.timeframe == timeframe)
        if direction:
            conditions.append(SMTModel.direction == direction)

        query = select(SMTModel).order_by(SMTModel.detection_timestamp.desc()).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest(
        self,
        primary_instrument: str,
        secondary_instrument: str,
        timeframe: str | None = None,
        limit: int = 10,
    ) -> list[SMTModel]:
        """Get latest SMT signals for a pair."""
        conditions = [
            SMTModel.primary_instrument == primary_instrument.upper(),
            SMTModel.secondary_instrument == secondary_instrument.upper(),
        ]
        if timeframe:
            conditions.append(SMTModel.timeframe == timeframe)

        result = await self.session.execute(
            select(SMTModel)
            .where(and_(*conditions))
            .order_by(SMTModel.detection_timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_statistics(
        self,
        primary_instrument: str | None = None,
        secondary_instrument: str | None = None,
        timeframe: str | None = None,
    ) -> dict:
        """Get SMT statistics."""
        conditions = []
        if primary_instrument:
            conditions.append(SMTModel.primary_instrument == primary_instrument.upper())
        if secondary_instrument:
            conditions.append(SMTModel.secondary_instrument == secondary_instrument.upper())
        if timeframe:
            conditions.append(SMTModel.timeframe == timeframe)

        query = select(SMTModel)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        events = list(result.scalars().all())

        stats: dict = {"total": len(events), "by_direction": {}, "by_timeframe": {}}
        for e in events:
            stats["by_direction"][e.direction] = stats["by_direction"].get(e.direction, 0) + 1
            tf = e.timeframe
            if tf not in stats["by_timeframe"]:
                stats["by_timeframe"][tf] = {"bullish": 0, "bearish": 0}
            stats["by_timeframe"][tf][e.direction] += 1

        return stats

    async def get_pair_configs(self) -> list[PairConfigModel]:
        """Get all enabled pair configurations."""
        result = await self.session.execute(
            select(PairConfigModel).where(PairConfigModel.enabled == True)
        )
        return list(result.scalars().all())


def _summarize_directions(events: list[SMTEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in events:
        counts[e.direction] = counts.get(e.direction, 0) + 1
    return counts
