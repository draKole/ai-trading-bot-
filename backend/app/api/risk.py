"""Risk API endpoints — Risk Reports, Rules, Evaluations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.risk import (
    RiskService, RiskConfig, evaluate_risk,
)

router = APIRouter()


# ─── Evaluate ────────────────────────────────────────────────

@router.post("/evaluate")
async def evaluate(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate risk for the latest strategy setup."""
    from app.services.strategy import StrategyService

    strategy_service = StrategyService(db)
    risk_service = RiskService(db)

    setups = await strategy_service.get_setups(
        instrument=instrument, timeframe=timeframe, limit=1,
    )
    if not setups:
        raise HTTPException(404, f"No setups found for {instrument}")

    s = setups[0]
    setup_dict = {
        "setup_id": s.setup_id, "instrument": s.instrument,
        "timeframe": s.timeframe, "direction": s.direction,
        "preferred_entry": s.preferred_entry,
        "entry_zone_low": s.entry_zone_low,
        "entry_zone_high": s.entry_zone_high,
        "stop_reference": s.stop_reference,
        "target_1": s.target_1, "target_2": s.target_2, "target_3": s.target_3,
        "setup_score": s.setup_score,
    }

    biases = await strategy_service.get_bias(instrument=instrument, timeframe=timeframe, limit=1)
    bias_dict = None
    if biases:
        b = biases[0]
        bias_dict = {
            "direction": b.direction, "confidence": b.confidence,
            "trend": b.trend, "market_regime": b.market_regime,
            "session": b.session, "bias_grade": b.bias_grade,
            "strength_score": b.strength_score,
        }

    result = await risk_service.evaluate_and_store(
        setup=setup_dict, bias=bias_dict,
    )
    return result


@router.post("/evaluate-dry-run")
async def evaluate_dry_run(
    instrument: str = Query(...),
    timeframe: str = Query("5m"),
):
    """Evaluate risk without persisting — preview only."""
    setup_dict = {
        "setup_id": "dry-run-001",
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "direction": "bullish",
        "preferred_entry": 6010.0,
        "stop_reference": 6000.0,
        "target_1": 6030.0,
        "target_2": 6050.0,
        "setup_score": 85.0,
    }
    bias_dict = {
        "direction": "bullish",
        "confidence": "High",
        "trend": "bullish",
        "market_regime": "trending",
        "session": "london",
        "bias_grade": "A-",
        "strength_score": 85.0,
    }
    report = evaluate_risk(setup_dict, bias_dict)
    return report.to_dict()


# ─── Query ──────────────────────────────────────────────────

@router.get("/reports")
async def list_reports(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List risk reports."""
    risk_service = RiskService(db)
    reports = await risk_service.get_reports(
        instrument=instrument, timeframe=timeframe,
        classification=classification, limit=limit,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(reports),
        "reports": [
            {
                "id": r.id, "setup_id": r.setup_id,
                "classification": r.risk_classification,
                "score": r.overall_risk_score,
                "rr": round(r.reward_risk_ratio, 2),
                "direction": r.direction,
            }
            for r in reports
        ],
    }


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single risk report with evaluations."""
    risk_service = RiskService(db)
    report = await risk_service.get_report(report_id)
    if report is None:
        raise HTTPException(404, f"Report not found: {report_id}")

    evals = await risk_service.get_evaluations(report_id=report_id)
    return {
        "report": {
            "id": report.id, "setup_id": report.setup_id,
            "instrument": report.instrument, "direction": report.direction,
            "classification": report.risk_classification,
            "score": report.overall_risk_score,
            "rr": round(report.reward_risk_ratio, 2),
            "stop_pct": round(report.stop_distance_pct, 4),
            "expected_value": round(report.expected_value, 4),
            "stability": round(report.setup_stability_score, 1),
            "validation": report.validation_json,
            "failures": report.failure_reasons_json,
            "timestamp": report.created_at.isoformat(),
        },
        "evaluations": [
            {"rule": e.rule_name, "result": e.result, "detail": e.detail}
            for e in evals
        ],
    }


@router.get("/rules")
async def list_rules(
    db: AsyncSession = Depends(get_db),
):
    """List risk rules."""
    risk_service = RiskService(db)
    rules = await risk_service.get_rules()
    return {
        "count": len(rules),
        "rules": [
            {"name": r.name, "description": r.description,
             "rule_type": r.rule_type, "field": r.field,
             "threshold": r.threshold, "enabled": r.enabled}
            for r in rules
        ],
    }


@router.get("/statistics")
async def get_risk_statistics(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get risk statistics."""
    risk_service = RiskService(db)
    return await risk_service.get_statistics(
        instrument=instrument, timeframe=timeframe,
    )
