"""Strategy Service — persistence for Market Bias, Trade Setups, and evaluations."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_

from app.models.strategy import (
    MarketBias as BiasModel,
    TradeSetup as SetupModel,
    StrategyRule as RuleModel,
    StrategyEvaluation as EvalModel,
)
from app.services.strategy.engine import (
    build_market_bias, generate_trade_setup, evaluate_strategy_rules,
    MarketBias, TradeSetup, StrategyConfig, StrategyRule,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class StrategyService:
    """Service for Market Bias + Trade Setup generation and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_bias_and_setup(
        self,
        instrument: str,
        timeframe: str,
        timestamp: datetime,
        confluence_data: dict,
        ms_events: list[dict] | None = None,
        fvgs: list[dict] | None = None,
        order_blocks: list[dict] | None = None,
        smt_events: list[dict] | None = None,
        liquidity_events: list[dict] | None = None,
        liquidity_levels: list[dict] | None = None,
        swings: list[dict] | None = None,
        session: str = "unknown",
        config: StrategyConfig | None = None,
    ) -> dict:
        """Build bias, generate setup, evaluate rules, persist all."""
        if config is None:
            config = StrategyConfig()

        # Build Market Bias
        bias = build_market_bias(
            instrument=instrument, timeframe=timeframe, timestamp=timestamp,
            confluence_data=confluence_data, ms_events=ms_events,
            fvgs=fvgs, order_blocks=order_blocks, smt_events=smt_events,
            liquidity_events=liquidity_events, session=session, config=config,
        )

        # Persist bias
        db_bias = BiasModel(
            instrument=bias.instrument,
            timeframe=bias.timeframe,
            timestamp=bias.timestamp,
            direction=bias.direction,
            strength_score=bias.strength_score,
            confidence=bias.confidence,
            trend=bias.trend,
            market_regime=bias.market_regime,
            session=bias.session,
            bias_grade=bias.bias_grade,
            supporting_evidence_json=bias.supporting_evidence,
            contradicting_evidence_json=bias.contradicting_evidence,
            snapshot_id=bias.snapshot_id,
        )
        self.session.add(db_bias)
        await self.session.flush()

        # Generate Trade Setup
        setup = generate_trade_setup(
            bias=bias, order_blocks=order_blocks, fvgs=fvgs,
            liquidity_levels=liquidity_levels, swi_points=swings,
            config=config,
        )

        # Link bias to setup
        db_setup = SetupModel(
            setup_id=setup.setup_id,
            instrument=setup.instrument,
            timeframe=setup.timeframe,
            direction=setup.direction,
            status=setup.status,
            entry_zone_low=setup.entry_zone_low,
            entry_zone_high=setup.entry_zone_high,
            preferred_entry=setup.preferred_entry,
            stop_reference=setup.stop_reference,
            target_1=setup.target_1,
            target_2=setup.target_2,
            target_3=setup.target_3,
            required_confirmation_json=setup.required_confirmation,
            bias_id=db_bias.id,
            supporting_evidence_json=setup.supporting_evidence,
            contradictions_json=setup.contradictions,
            setup_score=setup.setup_score,
            setup_grade=setup.setup_grade,
            strategy_version=setup.strategy_version,
            generated_timestamp=setup.generated_timestamp,
            expires_at=setup.expires_at,
            config_snapshot=config.to_dict(),
        )
        self.session.add(db_setup)
        await self.session.flush()

        # Update bias with setup_id
        db_bias.setup_id = setup.setup_id
        self.session.add(db_bias)
        await self.session.flush()

        # Evaluate rules
        rule_results = evaluate_strategy_rules(setup, config.rules, config)

        for rr in rule_results:
            db_eval = EvalModel(
                setup_id=setup.setup_id,
                rule_name=rr["rule_name"],
                passed=rr["passed"],
                direction=rr["direction"],
                required_met=rr["required_met"],
                required_total=rr["required_total"],
                optional_met=rr["optional_met"],
                optional_total=rr["optional_total"],
                min_score=rr["min_score"],
                setup_score=rr["setup_score"],
                priority=rr["priority"],
                group=rr["group"],
            )
            self.session.add(db_eval)

        await self.session.flush()
        logger.info("strategy_setup_generated", setup_id=setup.setup_id,
                     instrument=instrument, direction=setup.direction,
                     grade=setup.setup_grade, score=setup.setup_score)

        return setup.to_dict()

    async def evaluate_only(
        self,
        setup: TradeSetup,
        config: StrategyConfig | None = None,
    ) -> list[dict]:
        """Evaluate rules without persisting."""
        if config is None:
            config = StrategyConfig()
        return evaluate_strategy_rules(setup, config.rules, config)

    async def get_setup(self, setup_id: str) -> SetupModel | None:
        result = await self.session.execute(
            select(SetupModel).where(SetupModel.setup_id == setup_id)
        )
        return result.scalar_one_or_none()

    async def get_setups(
        self,
        instrument: str,
        timeframe: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[SetupModel]:
        conditions = [SetupModel.instrument == instrument.upper()]
        if timeframe:
            conditions.append(SetupModel.timeframe == timeframe)
        if status:
            conditions.append(SetupModel.status == status)

        result = await self.session.execute(
            select(SetupModel)
            .where(and_(*conditions))
            .order_by(SetupModel.generated_timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_bias(
        self,
        instrument: str,
        timeframe: str | None = None,
        limit: int = 50,
    ) -> list[BiasModel]:
        conditions = [BiasModel.instrument == instrument.upper()]
        if timeframe:
            conditions.append(BiasModel.timeframe == timeframe)

        result = await self.session.execute(
            select(BiasModel)
            .where(and_(*conditions))
            .order_by(BiasModel.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_rules(
        self,
        group: str | None = None,
        direction: str | None = None,
        enabled_only: bool = True,
    ) -> list[RuleModel]:
        conditions = []
        if group:
            conditions.append(RuleModel.group == group)
        if direction:
            conditions.append(RuleModel.direction == direction)
        if enabled_only:
            conditions.append(RuleModel.enabled == True)

        query = select(RuleModel).order_by(RuleModel.priority.desc())
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_evaluations(
        self,
        setup_id: str | None = None,
        passed: bool | None = None,
        limit: int = 500,
    ) -> list[EvalModel]:
        conditions = []
        if setup_id:
            conditions.append(EvalModel.setup_id == setup_id)
        if passed is not None:
            conditions.append(EvalModel.passed == passed)

        query = select(EvalModel).order_by(EvalModel.priority.desc()).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_statistics(
        self,
        instrument: str,
        timeframe: str | None = None,
    ) -> dict:
        """Get strategy statistics."""
        conditions = [SetupModel.instrument == instrument.upper()]
        if timeframe:
            conditions.append(SetupModel.timeframe == timeframe)

        result = await self.session.execute(
            select(SetupModel).where(and_(*conditions))
        )
        setups = list(result.scalars().all())

        by_status = {}
        by_direction = {}
        by_grade = {}
        for s in setups:
            by_status[s.status] = by_status.get(s.status, 0) + 1
            by_direction[s.direction] = by_direction.get(s.direction, 0) + 1
            by_grade[s.setup_grade] = by_grade.get(s.setup_grade, 0) + 1

        return {
            "instrument": instrument.upper(),
            "total_setups": len(setups),
            "by_status": by_status,
            "by_direction": by_direction,
            "by_grade": by_grade,
        }
