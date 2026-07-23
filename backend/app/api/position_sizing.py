"""Position Sizing API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.position_sizing import (
    PositionSizingService, AccountConfig, calculate_position,
)

router = APIRouter()


@router.post("/calculate")
async def calculate(
    instrument: str = Query(...),
    timeframe: str = Query("5m"),
    db: AsyncSession = Depends(get_db),
):
    """Calculate position size for the latest strategy setup."""
    from app.services.strategy import StrategyService
    from app.services.risk import RiskService

    strategy_service = StrategyService(db)
    risk_service = RiskService(db)
    sizing_service = PositionSizingService(db)

    setups = await strategy_service.get_setups(
        instrument=instrument, timeframe=timeframe, limit=1,
    )
    if not setups:
        raise HTTPException(404, f"No setups found for {instrument}")

    s = setups[0]
    setup_dict = {
        "setup_id": s.setup_id,
        "instrument": s.instrument,
        "timeframe": s.timeframe,
        "direction": s.direction,
        "preferred_entry": s.preferred_entry,
        "entry_zone_low": s.entry_zone_low,
        "entry_zone_high": s.entry_zone_high,
        "stop_reference": s.stop_reference,
    }

    risk_reports = await risk_service.get_reports(instrument=instrument, limit=1)
    risk_dict = None
    if risk_reports:
        r = risk_reports[0]
        risk_dict = {
            "assessment": {
                "stop_distance_points": r.stop_distance_pct * float(
                    s.preferred_entry or 6000
                ) / 100,
            }
        }

    result = await sizing_service.calculate_and_store(
        setup=setup_dict, risk_report=risk_dict,
    )
    return result


@router.post("/calculate-dry-run")
async def calculate_dry_run(
    instrument: str = Query("ES"),
    entry_price: float = Query(6010.0),
    stop_price: float = Query(6000.0),
    direction: str = Query("bullish"),
    sizing_method: str = Query("fixed_percentage"),
    account_balance: float = Query(100000.0),
):
    """Preview position sizing without persistence."""
    setup = {
        "setup_id": "dry-run-001",
        "instrument": instrument.upper(),
        "direction": direction,
        "preferred_entry": entry_price,
        "stop_reference": stop_price,
    }
    config = AccountConfig(
        account_balance=account_balance,
        sizing_method=sizing_method,
    )
    rec = calculate_position(setup, config=config)
    return rec.to_dict()


@router.get("/recommendations")
async def list_recommendations(
    instrument: str = Query(...),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List position recommendations."""
    sizing_service = PositionSizingService(db)
    recs = await sizing_service.get_recommendations(instrument=instrument, limit=limit)
    return {
        "instrument": instrument.upper(),
        "count": len(recs),
        "recommendations": [
            {
                "recommendation_id": r.recommendation_id,
                "setup_id": r.setup_id,
                "direction": r.direction,
                "method": r.sizing_method,
                "contracts": r.recommended_contracts,
                "risk": round(r.total_dollar_risk, 2),
                "margin": round(r.margin_required, 2),
                "all_pass": r.all_constraints_pass,
            }
            for r in recs
        ],
    }


@router.get("/recommendations/{recommendation_id}")
async def get_recommendation(
    recommendation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single recommendation with evaluations."""
    sizing_service = PositionSizingService(db)
    rec = await sizing_service.get_recommendation(recommendation_id)
    if rec is None:
        raise HTTPException(404, f"Recommendation not found: {recommendation_id}")

    evals = await sizing_service.get_evaluations(
        recommendation_id=recommendation_id,
    )
    return {
        "recommendation": {
            "recommendation_id": rec.recommendation_id,
            "setup_id": rec.setup_id,
            "instrument": rec.instrument,
            "direction": rec.direction,
            "method": rec.sizing_method,
            "recommended_contracts": rec.recommended_contracts,
            "conservative_contracts": rec.conservative_contracts,
            "max_allowable_contracts": rec.max_allowable_contracts,
            "dollar_risk": round(rec.total_dollar_risk, 2),
            "margin": round(rec.margin_required, 2),
            "capital_utilization_pct": rec.capital_utilization_pct,
            "leverage": rec.effective_leverage,
            "risk_pct": rec.risk_pct_of_account,
            "all_pass": rec.all_constraints_pass,
            "failures": rec.failure_reasons_json,
        },
        "evaluations": [
            {"rule": e.rule_name, "status": e.status, "detail": e.detail}
            for e in evals
        ],
    }


@router.get("/rules")
async def list_rules(
    db: AsyncSession = Depends(get_db),
):
    """List position sizing rules."""
    sizing_service = PositionSizingService(db)
    rules = await sizing_service.get_rules()
    return {
        "count": len(rules),
        "rules": [
            {"name": r.name, "description": r.description,
             "rule_type": r.rule_type, "threshold": r.threshold,
             "enabled": r.enabled}
            for r in rules
        ],
    }


@router.get("/statistics")
async def get_sizing_statistics(
    instrument: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get position sizing statistics."""
    sizing_service = PositionSizingService(db)
    return await sizing_service.get_statistics(instrument=instrument)
