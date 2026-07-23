"""Risk Service — persistence for Risk Reports, Rules, and Evaluations."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_

from app.models.risk import (
    RiskReport as ReportModel,
    RiskRule as RuleModel,
    RiskEvaluation as EvalModel,
)
from app.services.risk.engine import (
    evaluate_risk, RiskConfig, RiskReport, ValidationSummary,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class RiskService:
    """Service for risk evaluation and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate_and_store(
        self,
        setup: dict,
        bias: dict | None = None,
        volatility_pct: float = 0.0,
        config: RiskConfig | None = None,
    ) -> dict:
        """Evaluate risk and persist report."""
        if config is None:
            config = RiskConfig()

        report = evaluate_risk(setup, bias, volatility_pct, config)

        # Persist report
        db_report = ReportModel(
            setup_id=report.setup_id,
            instrument=report.instrument,
            timeframe=report.timeframe,
            direction=report.direction,
            overall_risk_score=report.overall_risk_score,
            risk_classification=report.risk_classification,
            reward_risk_ratio=report.assessment.reward_risk_ratio,
            stop_distance_pct=report.assessment.stop_distance_pct,
            mfe_estimate=report.assessment.mfe_estimate,
            expected_value=report.assessment.expected_value,
            volatility_pct=report.assessment.volatility_pct,
            setup_stability_score=report.assessment.setup_stability_score,
            validation_json=report.validation.to_dict(),
            supporting_evidence_json=report.supporting_evidence,
            contradicting_evidence_json=report.contradicting_evidence,
            failure_reasons_json=report.failure_reasons,
            config_snapshot=config.to_dict(),
        )
        self.session.add(db_report)
        await self.session.flush()

        # Persist individual evaluations
        for item in report.validation.items:
            db_eval = EvalModel(
                report_id=db_report.id,
                setup_id=report.setup_id,
                rule_name=item.rule,
                result=item.result,
                detail=item.detail,
            )
            self.session.add(db_eval)

        await self.session.flush()
        logger.info("risk_report_generated", setup_id=report.setup_id,
                     classification=report.risk_classification,
                     score=report.overall_risk_score)

        return report.to_dict()

    async def get_report(self, report_id: int) -> ReportModel | None:
        result = await self.session.execute(
            select(ReportModel).where(ReportModel.id == report_id)
        )
        return result.scalar_one_or_none()

    async def get_reports(
        self,
        instrument: str,
        timeframe: str | None = None,
        classification: str | None = None,
        limit: int = 100,
    ) -> list[ReportModel]:
        conditions = [ReportModel.instrument == instrument.upper()]
        if timeframe:
            conditions.append(ReportModel.timeframe == timeframe)
        if classification:
            conditions.append(ReportModel.risk_classification == classification)

        result = await self.session.execute(
            select(ReportModel)
            .where(and_(*conditions))
            .order_by(ReportModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_rules(self, enabled_only: bool = True) -> list[RuleModel]:
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
        report_id: int | None = None,
        setup_id: str | None = None,
        result: str | None = None,
        limit: int = 1000,
    ) -> list[EvalModel]:
        conditions = []
        if report_id:
            conditions.append(EvalModel.report_id == report_id)
        if setup_id:
            conditions.append(EvalModel.setup_id == setup_id)
        if result:
            conditions.append(EvalModel.result == result)

        query = select(EvalModel).order_by(EvalModel.created_at.desc()).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result_obj = await self.session.execute(query)
        return list(result_obj.scalars().all())

    async def get_statistics(
        self,
        instrument: str,
        timeframe: str | None = None,
    ) -> dict:
        conditions = [ReportModel.instrument == instrument.upper()]
        if timeframe:
            conditions.append(ReportModel.timeframe == timeframe)

        result = await self.session.execute(
            select(ReportModel).where(and_(*conditions))
        )
        reports = list(result.scalars().all())

        by_class = {}
        avg_rr = 0.0
        count = len(reports)

        for r in reports:
            by_class[r.risk_classification] = by_class.get(r.risk_classification, 0) + 1
            avg_rr += r.reward_risk_ratio

        if count > 0:
            avg_rr /= count

        return {
            "instrument": instrument.upper(),
            "total_reports": count,
            "by_classification": by_class,
            "avg_reward_risk": round(avg_rr, 2),
        }
