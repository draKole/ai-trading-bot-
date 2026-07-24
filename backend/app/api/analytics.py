"""Performance Analytics API endpoints."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.analytics import (
    AnalyticsService, AnalyticsController, compare_strategies,
)

router = APIRouter()


@router.post("/generate")
async def generate_report(
    run_id: int = Query(...),
    trades_json: str = Query("[]", description="JSON array of trade dicts"),
    metrics_json: str = Query("{}", description="JSON metrics dict"),
    equity_json: str = Query("[]", description="JSON equity curve points"),
    db: AsyncSession = Depends(get_db),
):
    """Generate and persist an analytics report."""
    service = AnalyticsService(db)

    trades = json.loads(trades_json)
    metrics = json.loads(metrics_json)
    equity_points = json.loads(equity_json)

    controller = AnalyticsController()
    report = controller.analyze(
        run_data={"id": run_id},
        trades=trades,
        metrics=metrics,
        equity_points=equity_points,
    )

    result = await service.store_report(run_id, report)
    return {"report_id": result["id"], "summary": report.get("executive_summary", {})}


@router.post("/compare")
async def compare_runs(
    runs_json: str = Query(..., description="JSON array of {run_id, metrics} dicts"),
    db: AsyncSession = Depends(get_db),
):
    """Compare multiple backtest runs."""
    service = AnalyticsService(db)
    runs_data = json.loads(runs_json)
    comparison = compare_strategies(runs_data)

    run_ids = [r.get("run_id", 0) for r in runs_data if r.get("run_id")]
    await service.store_comparison(run_ids, comparison)

    return comparison


@router.get("/reports")
async def list_reports(
    run_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List analytics reports."""
    service = AnalyticsService(db)
    reports = await service.get_reports(run_id=run_id, limit=limit)
    return {"count": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a full analytics report."""
    service = AnalyticsService(db)
    report = await service.get_report(report_id)
    if report is None:
        raise HTTPException(404, f"Report not found: {report_id}")
    return report


@router.get("/reports/{report_id}/summary")
async def get_report_summary(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get just the executive summary."""
    service = AnalyticsService(db)
    summary = await service.get_report_summary(report_id)
    if summary is None:
        raise HTTPException(404, f"Report not found: {report_id}")
    return summary


@router.get("/reports/{report_id}/charts")
async def get_report_charts(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get just the chart datasets."""
    service = AnalyticsService(db)
    charts = await service.get_report_charts(report_id)
    if charts is None:
        raise HTTPException(404, f"Report not found: {report_id}")
    return charts


@router.get("/statistics")
async def get_statistics(
    db: AsyncSession = Depends(get_db),
):
    """Global analytics statistics."""
    service = AnalyticsService(db)
    return await service.get_statistics()
