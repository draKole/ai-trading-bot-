"""Strategy API endpoints — Market Bias, Trade Setups, Rule Evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.strategy import (
    StrategyService, StrategyConfig,
    build_market_bias, generate_trade_setup, evaluate_strategy_rules,
    MarketBias, TradeSetup,
)

router = APIRouter()


def _to_dict_list(objs, fields_map: dict) -> list[dict]:
    result = []
    for obj in objs:
        d = {}
        for src, dst in fields_map.items():
            val = getattr(obj, src, None)
            if isinstance(val, datetime):
                val = val.isoformat()
            d[dst] = val
        result.append(d)
    return result


# ─── Evaluate (full pipeline) ───────────────────────────────

@router.post("/evaluate")
async def evaluate(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    session: str = Query("unknown"),
    db: AsyncSession = Depends(get_db),
):
    """Generate Market Bias + Trade Setup from current market data."""
    from app.services.market_data import MarketDataService
    from app.services.market_structure.service import MarketStructureService
    from app.services.liquidity.service import LiquidityService
    from app.services.fvg.service import FVGService
    from app.services.order_block.service import OrderBlockService
    from app.services.smt.service import SMTService
    from app.services.confluence.service import ConfluenceService

    md_service = MarketDataService(db)
    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(404, f"Instrument not found: {instrument}")

    now = datetime.utcnow()
    inst_id = inst.id

    # Gather data
    ms_service = MarketStructureService(db)
    ms_events = await ms_service.get_events(instrument_id=inst_id, timeframe=timeframe, limit=1000)
    ms_list = _to_dict_list(ms_events or [], {
        "id": "id", "event_type": "event_type", "direction": "direction",
        "price_level": "price_level", "bar_timestamp": "timestamp",
    })

    liq_service = LiquidityService(db)
    liq_events = await liq_service.get_events(instrument_id=inst_id, timeframe=timeframe, limit=500)
    liq_list = _to_dict_list(liq_events or [], {
        "id": "id", "event_type": "event_type", "direction": "direction",
    })

    fvg_service = FVGService(db)
    fvgs = await fvg_service.get_active_fvgs(instrument_id=inst_id, timeframe=timeframe, status=None)
    fvg_list = _to_dict_list(fvgs, {
        "id": "id", "direction": "direction", "status": "status",
    })

    ob_service = OrderBlockService(db)
    obs = await ob_service.get_active_obs(instrument_id=inst_id, timeframe=timeframe, status=None)
    ob_list = _to_dict_list(obs, {
        "id": "id", "direction": "direction", "status": "status",
        "price_high": "price_high", "price_low": "price_low", "price_level": "price_level",
    })

    smt_service = SMTService(db)
    smt_list_raw = await smt_service.get_latest(
        primary_instrument=instrument, secondary_instrument="",
        timeframe=timeframe, limit=100,
    )
    smt_list = _to_dict_list(smt_list_raw or [], {"id": "id", "direction": "direction"})

    # Confluence for trend data
    confluence_service = ConfluenceService(db)
    confluence_snapshots = await confluence_service.get_snapshots(
        instrument=instrument, timeframe=timeframe, limit=1,
    )
    confluence_data = {}
    if confluence_snapshots:
        cs = confluence_snapshots[0]
        confluence_data = {
            "snapshot_id": cs.id,
            "trend": cs.trend,
            "swing_direction": cs.swing_direction,
            "bullish_signals": cs.bullish_signals,
            "bearish_signals": cs.bearish_signals,
            "agreement_ratio": cs.agreement_ratio,
        }

    strategy_service = StrategyService(db)
    result = await strategy_service.build_bias_and_setup(
        instrument=instrument.upper(), timeframe=timeframe, timestamp=now,
        confluence_data=confluence_data,
        ms_events=ms_list, fvgs=fvg_list, order_blocks=ob_list,
        smt_events=smt_list, liquidity_events=liq_list,
        liquidity_levels=[], swings=[], session=session,
    )
    return result


@router.post("/evaluate-dry-run")
async def evaluate_dry_run(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    direction: str = Query("bullish"),
    session: str = Query("unknown"),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate without persisting — returns bias + setup preview."""
    now = datetime.utcnow()

    confluence_data = {
        "trend": direction, "swing_direction": direction,
        "bullish_signals": 0, "bearish_signals": 0, "agreement_ratio": 0,
    }

    ms_events = [{"id": 1, "event_type": "BOS", "direction": direction}]
    fvgs = [{"id": 1, "direction": direction, "status": "active"}]
    obs = [{"id": 1, "direction": direction, "status": "active",
            "price_high": 100.0, "price_low": 99.0, "price_level": 99.5}]
    swings = [{"swing_type": "low" if direction == "bullish" else "high",
               "price": 98.0}]

    config = StrategyConfig()
    bias = build_market_bias(
        instrument=instrument.upper(), timeframe=timeframe, timestamp=now,
        confluence_data=confluence_data, ms_events=ms_events,
        fvgs=fvgs, order_blocks=obs, session=session, config=config,
    )

    setup = generate_trade_setup(bias=bias, order_blocks=obs, fvgs=fvgs,
                                 swi_points=swings, config=config)
    rules = evaluate_strategy_rules(setup, config.rules, config)

    return {
        "bias": bias.to_dict(),
        "setup": setup.to_dict(),
        "rule_results": rules,
    }


# ─── Query ──────────────────────────────────────────────────

@router.get("/setups")
async def list_setups(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List trade setups."""
    strategy_service = StrategyService(db)
    setups = await strategy_service.get_setups(
        instrument=instrument, timeframe=timeframe, status=status, limit=limit,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(setups),
        "setups": [
            {
                "setup_id": s.setup_id, "direction": s.direction,
                "status": s.status, "grade": s.setup_grade,
                "score": s.setup_score, "entry_low": s.entry_zone_low,
                "entry_high": s.entry_zone_high, "stop": s.stop_reference,
                "generated": s.generated_timestamp.isoformat(),
            }
            for s in setups
        ],
    }


@router.get("/setups/{setup_id}")
async def get_setup(
    setup_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific setup with evaluations."""
    strategy_service = StrategyService(db)
    setup = await strategy_service.get_setup(setup_id)
    if setup is None:
        raise HTTPException(404, f"Setup not found: {setup_id}")

    evals = await strategy_service.get_evaluations(setup_id=setup_id)
    bias = None
    if setup.bias_id:
        biases = await strategy_service.get_bias(instrument=setup.instrument, limit=100)
        for b in biases:
            if b.id == setup.bias_id:
                bias = b
                break

    return {
        "setup": {
            "setup_id": setup.setup_id, "instrument": setup.instrument,
            "timeframe": setup.timeframe, "direction": setup.direction,
            "status": setup.status,
            "entry_zone_low": setup.entry_zone_low,
            "entry_zone_high": setup.entry_zone_high,
            "preferred_entry": setup.preferred_entry,
            "stop_reference": setup.stop_reference,
            "target_1": setup.target_1, "target_2": setup.target_2,
            "target_3": setup.target_3,
            "setup_score": setup.setup_score, "setup_grade": setup.setup_grade,
            "generated": setup.generated_timestamp.isoformat(),
            "expires": setup.expires_at.isoformat() if setup.expires_at else None,
        },
        "bias": {
            "direction": bias.direction, "strength": bias.strength_score,
            "confidence": bias.confidence, "grade": bias.bias_grade,
            "regime": bias.market_regime,
        } if bias else None,
        "evaluations": [
            {"rule": e.rule_name, "passed": e.passed, "group": e.group}
            for e in evals
        ],
    }


@router.get("/bias")
async def get_current_bias(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get recent market biases."""
    strategy_service = StrategyService(db)
    biases = await strategy_service.get_bias(
        instrument=instrument, timeframe=timeframe, limit=limit,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(biases),
        "biases": [
            {
                "direction": b.direction, "strength": b.strength_score,
                "confidence": b.confidence, "grade": b.bias_grade,
                "trend": b.trend, "regime": b.market_regime,
                "session": b.session, "timestamp": b.timestamp.isoformat(),
            }
            for b in biases
        ],
    }


@router.get("/rules")
async def list_rules(
    group: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List strategy rules."""
    strategy_service = StrategyService(db)
    rules = await strategy_service.get_rules(
        group=group, direction=direction,
    )
    return {
        "count": len(rules),
        "rules": [
            {
                "name": r.name, "description": r.description,
                "direction": r.direction, "group": r.group,
                "priority": r.priority, "min_score": r.min_score,
                "enabled": r.enabled,
            }
            for r in rules
        ],
    }


@router.get("/statistics")
async def get_strategy_statistics(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get strategy statistics."""
    strategy_service = StrategyService(db)
    return await strategy_service.get_statistics(
        instrument=instrument, timeframe=timeframe,
    )
