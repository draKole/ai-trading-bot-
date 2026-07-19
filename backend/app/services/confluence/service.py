"""Confluence Service — snapshot building and rule evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_

from app.models.confluence import (
    ConfluenceSnapshot as SnapshotModel,
    ConfluenceRuleResult as ResultModel,
    ConfluenceRule as RuleModel,
)
from app.services.confluence.engine import (
    build_snapshot, evaluate_rules,
    ConfluenceConfig, ConfluenceSnapshot, Rule, RuleResult,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class ConfluenceService:
    """Service for confluence snapshot building and rule evaluation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_and_store(
        self,
        instrument: str,
        timeframe: str,
        timestamp: datetime,
        ms_events: list[dict] | None = None,
        liquidity_events: list[dict] | None = None,
        fvgs: list[dict] | None = None,
        order_blocks: list[dict] | None = None,
        smt_events: list[dict] | None = None,
        session: str = "unknown",
        config: ConfluenceConfig | None = None,
    ) -> dict:
        """Build snapshot, evaluate rules, and store results."""
        if config is None:
            config = ConfluenceConfig()

        snapshot = build_snapshot(
            instrument=instrument, timeframe=timeframe, timestamp=timestamp,
            ms_events=ms_events, liquidity_events=liquidity_events,
            fvgs=fvgs, order_blocks=order_blocks, smt_events=smt_events,
            session=session, config=config,
        )

        # Store snapshot
        db_snapshot = SnapshotModel(
            instrument=snapshot.instrument,
            timeframe=snapshot.timeframe,
            timestamp=snapshot.timestamp,
            trend=snapshot.trend,
            trend_confidence=snapshot.trend_confidence,
            ms_event_count=snapshot.ms_event_count,
            ms_bullish_count=snapshot.ms_bullish_count,
            ms_bearish_count=snapshot.ms_bearish_count,
            swing_direction=snapshot.swing_direction,
            latest_bos_json=snapshot.latest_bos,
            latest_choch_json=snapshot.latest_choch,
            liquidity_level_count=snapshot.liquidity_level_count,
            active_sweeps_count=snapshot.active_sweeps_count,
            active_sweeps_bullish=snapshot.active_sweeps_bullish,
            active_sweeps_bearish=snapshot.active_sweeps_bearish,
            fvg_active_count=snapshot.fvg_active_count,
            fvg_bullish_count=snapshot.fvg_bullish_count,
            fvg_bearish_count=snapshot.fvg_bearish_count,
            fvg_mitigated_count=snapshot.fvg_mitigated_count,
            ob_active_count=snapshot.ob_active_count,
            ob_bullish_count=snapshot.ob_bullish_count,
            ob_bearish_count=snapshot.ob_bearish_count,
            ob_mitigated_count=snapshot.ob_mitigated_count,
            smt_active_count=snapshot.smt_active_count,
            smt_bullish_count=snapshot.smt_bullish_count,
            smt_bearish_count=snapshot.smt_bearish_count,
            session=snapshot.session,
            session_aligned=snapshot.session_aligned,
            bullish_signals=snapshot.bullish_signals,
            bearish_signals=snapshot.bearish_signals,
            neutral_signals=snapshot.neutral_signals,
            total_signals=snapshot.total_signals,
            agreement_ratio=snapshot.agreement_ratio,
            config_snapshot=config.to_dict(),
        )
        self.session.add(db_snapshot)
        await self.session.flush()

        # Evaluate rules
        rules = config.rules
        results = evaluate_rules(snapshot, rules, config)

        # Store rule results
        for result in results:
            db_result = ResultModel(
                snapshot_id=db_snapshot.id,
                rule_name=result.rule_name,
                matched=result.matched,
                direction=result.direction,
                match_count=result.match_count,
                total_conditions=result.total_conditions,
                score=result.score,
                matched_conditions_json=result.matched_conditions,
                evidence_json=result.evidence,
            )
            self.session.add(db_result)

        await self.session.flush()

        matched_rules = [r for r in results if r.matched]
        logger.info("confluence_snapshot_built",
                     instrument=instrument, timeframe=timeframe,
                     trend=snapshot.trend, rules_matched=len(matched_rules))

        return {
            "snapshot_id": db_snapshot.id,
            "instrument": instrument,
            "timeframe": timeframe,
            "trend": snapshot.trend,
            "trend_confidence": round(snapshot.trend_confidence, 1),
            "bullish_signals": snapshot.bullish_signals,
            "bearish_signals": snapshot.bearish_signals,
            "agreement_ratio": round(snapshot.agreement_ratio, 2),
            "rules_evaluated": len(results),
            "rules_matched": len(matched_rules),
            "matched_rules": [
                {"name": r.rule_name, "direction": r.direction, "score": round(r.score, 1)}
                for r in matched_rules
            ],
        }

    async def get_snapshot(self, snapshot_id: int) -> SnapshotModel | None:
        result = await self.session.execute(
            select(SnapshotModel).where(SnapshotModel.id == snapshot_id)
        )
        return result.scalar_one_or_none()

    async def get_snapshots(
        self,
        instrument: str,
        timeframe: str | None = None,
        limit: int = 100,
    ) -> list[SnapshotModel]:
        conditions = [SnapshotModel.instrument == instrument.upper()]
        if timeframe:
            conditions.append(SnapshotModel.timeframe == timeframe)

        result = await self.session.execute(
            select(SnapshotModel)
            .where(and_(*conditions))
            .order_by(SnapshotModel.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_rule_results(
        self,
        snapshot_id: int | None = None,
        matched: bool | None = None,
        limit: int = 500,
    ) -> list[ResultModel]:
        conditions = []
        if snapshot_id:
            conditions.append(ResultModel.snapshot_id == snapshot_id)
        if matched is not None:
            conditions.append(ResultModel.matched == matched)

        query = select(ResultModel).order_by(ResultModel.score.desc()).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_rules(
        self,
        group: str | None = None,
        enabled_only: bool = True,
    ) -> list[RuleModel]:
        conditions = []
        if group:
            conditions.append(RuleModel.group == group)
        if enabled_only:
            conditions.append(RuleModel.enabled == True)

        query = select(RuleModel).order_by(RuleModel.weight.desc())
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_statistics(
        self,
        instrument: str,
        timeframe: str | None = None,
    ) -> dict:
        """Get confluence statistics."""
        conditions = [SnapshotModel.instrument == instrument.upper()]
        if timeframe:
            conditions.append(SnapshotModel.timeframe == timeframe)

        result = await self.session.execute(
            select(SnapshotModel).where(and_(*conditions))
        )
        snapshots = list(result.scalars().all())

        trends = {}
        for s in snapshots:
            trends[s.trend] = trends.get(s.trend, 0) + 1

        return {
            "instrument": instrument.upper(),
            "total_snapshots": len(snapshots),
            "by_trend": trends,
        }
