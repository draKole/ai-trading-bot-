"""Analytics Persistence Service — report and comparison CRUD."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_, desc

from app.models.analytics import AnalyticsReport, StrategyComparison

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class AnalyticsService:
    """Service for analytics report and comparison persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def store_report(self, run_id: int, report: dict) -> dict:
        """Store an analytics report."""
        import json as _json
        db_report = AnalyticsReport(
            run_id=run_id,
            report_type=report.get("report_type", "full"),
            metrics_json=_json.dumps(report, default=str),
            charts_json=_json.dumps(report.get("charts", {}), default=str),
            summary_json=_json.dumps(report.get("executive_summary", {}), default=str),
        )
        self.session.add(db_report)
        await self.session.flush()
        return {"id": db_report.id, "run_id": run_id, "report_type": db_report.report_type}

    async def get_report(self, report_id: int) -> dict | None:
        """Get a report by ID."""
        result = await self.session.execute(
            select(AnalyticsReport).where(AnalyticsReport.id == report_id)
        )
        r = result.scalar_one_or_none()
        if r is None:
            return None
        return {
            "id": r.id, "run_id": r.run_id, "report_type": r.report_type,
            "metrics_json": r.metrics_json, "charts_json": r.charts_json,
            "summary_json": r.summary_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }

    async def get_reports(
        self, run_id: int | None = None, limit: int = 50,
    ) -> list[dict]:
        """List reports with optional run filter."""
        conditions = []
        if run_id is not None:
            conditions.append(AnalyticsReport.run_id == run_id)
        query = select(AnalyticsReport).order_by(desc(AnalyticsReport.created_at)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return [
            {"id": r.id, "run_id": r.run_id, "report_type": r.report_type,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in result.scalars().all()
        ]

    async def get_report_summary(self, report_id: int) -> dict | None:
        """Get just the summary portion of a report."""
        result = await self.session.execute(
            select(AnalyticsReport).where(AnalyticsReport.id == report_id)
        )
        r = result.scalar_one_or_none()
        if r is None:
            return None
        return {
            "id": r.id, "run_id": r.run_id,
            "summary": r.summary_json,
        }

    async def get_report_charts(self, report_id: int) -> dict | None:
        """Get just the charts portion of a report."""
        result = await self.session.execute(
            select(AnalyticsReport).where(AnalyticsReport.id == report_id)
        )
        r = result.scalar_one_or_none()
        if r is None:
            return None
        return {
            "id": r.id, "run_id": r.run_id,
            "charts": r.charts_json,
        }

    async def store_comparison(self, run_ids: list[int], comparison: dict) -> dict:
        """Store a strategy comparison."""
        import json as _json
        db_comp = StrategyComparison(
            run_ids=_json.dumps(run_ids),
            comparison_json=_json.dumps(comparison, default=str),
        )
        self.session.add(db_comp)
        await self.session.flush()
        return {"id": db_comp.id, "run_count": len(run_ids)}

    async def get_comparison(self, comp_id: int) -> dict | None:
        """Get a comparison by ID."""
        result = await self.session.execute(
            select(StrategyComparison).where(StrategyComparison.id == comp_id)
        )
        c = result.scalar_one_or_none()
        if c is None:
            return None
        return {
            "id": c.id, "run_ids": c.run_ids,
            "comparison_json": c.comparison_json,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }

    async def get_statistics(self) -> dict:
        """Global analytics statistics."""
        result = await self.session.execute(select(AnalyticsReport))
        reports = list(result.scalars().all())
        comp_result = await self.session.execute(select(StrategyComparison))
        comparisons = list(comp_result.scalars().all())
        return {
            "total_reports": len(reports),
            "total_comparisons": len(comparisons),
        }
