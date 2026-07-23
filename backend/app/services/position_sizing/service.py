"""Position Sizing Service — persistence layer."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_

from app.models.position_sizing import (
    PositionRecommendation as RecModel,
    PositionSizingRule as RuleModel,
    PositionSizingEvaluation as EvalModel,
)
from app.services.position_sizing.engine import (
    calculate_position, AccountConfig, PositionRecommendation,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class PositionSizingService:
    """Service for position sizing and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_and_store(
        self,
        setup: dict,
        risk_report: dict | None = None,
        config: AccountConfig | None = None,
        open_positions: int = 0,
        daily_loss_so_far: float = 0.0,
    ) -> dict:
        """Calculate position size and persist recommendation."""
        if config is None:
            config = AccountConfig()

        rec = calculate_position(setup, risk_report, config,
                                  open_positions, daily_loss_so_far)

        db_rec = RecModel(
            recommendation_id=rec.recommendation_id,
            setup_id=rec.setup_id,
            instrument=rec.instrument,
            direction=rec.direction,
            sizing_method=rec.sizing_method,
            recommended_contracts=rec.recommended_contracts,
            conservative_contracts=rec.conservative_contracts,
            max_allowable_contracts=rec.max_allowable_contracts,
            dollar_risk_per_contract=rec.dollar_risk_per_contract,
            total_dollar_risk=rec.total_dollar_risk,
            margin_required=rec.margin_required,
            capital_utilization_pct=rec.capital_utilization_pct,
            effective_leverage=rec.effective_leverage,
            risk_pct_of_account=rec.risk_pct_of_account,
            constraint_results_json=rec.constraint_results,
            all_constraints_pass=rec.all_constraints_pass,
            failure_reasons_json=rec.failure_reasons,
            config_snapshot=config.to_dict(),
        )
        self.session.add(db_rec)
        await self.session.flush()

        for cr in rec.constraint_results:
            db_eval = EvalModel(
                recommendation_id=rec.recommendation_id,
                setup_id=rec.setup_id,
                rule_name=cr["rule"],
                status=cr["status"],
                detail=cr["detail"],
            )
            self.session.add(db_eval)

        await self.session.flush()
        logger.info("position_sizing_calculated",
                     recommendation_id=rec.recommendation_id,
                     contracts=rec.recommended_contracts,
                     method=rec.sizing_method)

        return rec.to_dict()

    async def get_recommendation(
        self, recommendation_id: str,
    ) -> RecModel | None:
        result = await self.session.execute(
            select(RecModel).where(
                RecModel.recommendation_id == recommendation_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_recommendations(
        self,
        instrument: str,
        limit: int = 100,
    ) -> list[RecModel]:
        result = await self.session.execute(
            select(RecModel)
            .where(RecModel.instrument == instrument.upper())
            .order_by(RecModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_rules(
        self, enabled_only: bool = True,
    ) -> list[RuleModel]:
        conditions = []
        if enabled_only:
            conditions.append(RuleModel.enabled == True)
        query = select(RuleModel).order_by(RuleModel.priority.desc())
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_evaluations(
        self,
        recommendation_id: str | None = None,
        limit: int = 500,
    ) -> list[EvalModel]:
        conditions = []
        if recommendation_id:
            conditions.append(EvalModel.recommendation_id == recommendation_id)
        query = select(EvalModel).order_by(EvalModel.created_at.desc()).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_statistics(
        self, instrument: str,
    ) -> dict:
        result = await self.session.execute(
            select(RecModel).where(RecModel.instrument == instrument.upper())
        )
        recs = list(result.scalars().all())

        total = len(recs)
        avg_contracts = sum(r.recommended_contracts for r in recs) / max(total, 1)
        passed = sum(1 for r in recs if r.all_constraints_pass)

        return {
            "instrument": instrument.upper(),
            "total_recommendations": total,
            "avg_recommended_contracts": round(avg_contracts, 1),
            "constraints_pass_rate": round(passed / max(total, 1) * 100, 1),
        }
