"""Confluence API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.confluence import (
    ConfluenceService, ConfluenceConfig, build_snapshot, evaluate_rules,
    Rule, RuleCondition,
)
from app.services.market_data import MarketDataService
from app.services.market_structure.service import MarketStructureService
from app.services.liquidity.service import LiquidityService
from app.services.fvg.service import FVGService
from app.services.order_block.service import OrderBlockService
from app.services.smt.service import SMTService

router = APIRouter()


def _to_dict_list(objs, fields_map: dict) -> list[dict]:
    """Convert ORM objects to dicts using field mappings."""
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


# ─── Snapshot Building ───────────────────────────────────────

@router.post("/snapshot")
async def create_snapshot(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    session: str = Query("unknown"),
    db: AsyncSession = Depends(get_db),
):
    """Build and store a confluence snapshot for the current market state."""
    md_service = MarketDataService(db)
    confluence_service = ConfluenceService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(404, f"Instrument not found: {instrument}")

    now = datetime.utcnow()
    inst_id = inst.id

    # Gather data from all engines
    ms_service = MarketStructureService(db)
    ms_events = await ms_service.get_events(instrument_id=inst_id, timeframe=timeframe, limit=1000)
    ms_list = _to_dict_list(ms_events or [], {
        "bar_index": "bar_index", "event_type": "event_type",
        "direction": "direction", "price_level": "price_level",
        "bar_timestamp": "timestamp", "id": "id",
    })

    # Liquidity
    liq_service = LiquidityService(db)
    liq_events = await liq_service.get_events(instrument_id=inst_id, timeframe=timeframe, limit=500)
    liq_list = _to_dict_list(liq_events or [], {
        "event_type": "event_type", "direction": "direction",
        "id": "id",
    })

    # FVGs
    fvg_service = FVGService(db)
    fvgs = await fvg_service.get_active_fvgs(instrument_id=inst_id, timeframe=timeframe, status=None)
    fvg_list = _to_dict_list(fvgs, {
        "direction": "direction", "status": "status", "id": "id",
    })

    # Order Blocks
    ob_service = OrderBlockService(db)
    obs = await ob_service.get_active_obs(instrument_id=inst_id, timeframe=timeframe, status=None)
    ob_list = _to_dict_list(obs, {
        "direction": "direction", "status": "status", "id": "id",
    })

    # SMT
    smt_service = SMTService(db)
    smt_events = await smt_service.get_latest(
        primary_instrument=instrument, secondary_instrument="",
        timeframe=timeframe, limit=100,
    )
    smt_list = _to_dict_list(smt_events or [], {
        "direction": "direction", "id": "id",
    })

    result = await confluence_service.build_and_store(
        instrument=instrument.upper(), timeframe=timeframe, timestamp=now,
        ms_events=ms_list, liquidity_events=liq_list,
        fvgs=fvg_list, order_blocks=ob_list, smt_events=smt_list,
        session=session,
    )
    return result


@router.post("/snapshot-dry-run")
async def dry_run_snapshot(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    session: str = Query("unknown"),
    db: AsyncSession = Depends(get_db),
):
    """Build and evaluate snapshot without storing."""
    md_service = MarketDataService(db)
    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(404, f"Instrument not found: {instrument}")

    now = datetime.utcnow()
    snapshot = build_snapshot(
        instrument=instrument.upper(), timeframe=timeframe, timestamp=now,
        ms_events=[], liquidity_events=[], fvgs=[], order_blocks=[],
        smt_events=[], session=session,
    )
    results = evaluate_rules(snapshot)

    return {
        "trend": snapshot.trend,
        "trend_confidence": round(snapshot.trend_confidence, 1),
        "bullish_signals": snapshot.bullish_signals,
        "bearish_signals": snapshot.bearish_signals,
        "agreement_ratio": round(snapshot.agreement_ratio, 2),
        "rules_evaluated": len(results),
        "rules_matched": len([r for r in results if r.matched]),
        "results": [
            {"name": r.rule_name, "matched": r.matched, "score": round(r.score, 1)}
            for r in results
        ],
    }


# ─── Query ───────────────────────────────────────────────────

@router.get("/snapshots")
async def list_snapshots(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List historical confluence snapshots."""
    confluence_service = ConfluenceService(db)
    snapshots = await confluence_service.get_snapshots(
        instrument=instrument, timeframe=timeframe, limit=limit,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(snapshots),
        "snapshots": [
            {
                "id": s.id,
                "timeframe": s.timeframe,
                "timestamp": s.timestamp.isoformat(),
                "trend": s.trend,
                "confidence": round(s.trend_confidence, 1),
                "bullish": s.bullish_signals,
                "bearish": s.bearish_signals,
                "agreement": round(s.agreement_ratio, 2),
            }
            for s in snapshots
        ],
    }


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific snapshot with its rule results."""
    confluence_service = ConfluenceService(db)
    snapshot = await confluence_service.get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(404, f"Snapshot not found: {snapshot_id}")

    results = await confluence_service.get_rule_results(snapshot_id=snapshot_id)
    return {
        "snapshot": {
            "id": snapshot.id,
            "instrument": snapshot.instrument,
            "timeframe": snapshot.timeframe,
            "timestamp": snapshot.timestamp.isoformat(),
            "trend": snapshot.trend,
            "trend_confidence": round(snapshot.trend_confidence, 1),
            "bullish_signals": snapshot.bullish_signals,
            "bearish_signals": snapshot.bearish_signals,
            "agreement_ratio": round(snapshot.agreement_ratio, 2),
        },
        "rule_results": [
            {
                "rule_name": r.rule_name,
                "matched": r.matched,
                "direction": r.direction,
                "score": round(r.score, 1),
            }
            for r in results
        ],
    }


@router.get("/rules")
async def list_rules(
    group: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List configured rules."""
    confluence_service = ConfluenceService(db)
    rules = await confluence_service.get_rules(group=group)
    return {
        "count": len(rules),
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "operator": r.operator,
                "group": r.group,
                "direction": r.direction,
                "weight": r.weight,
                "enabled": r.enabled,
            }
            for r in rules
        ],
    }


@router.get("/statistics")
async def get_confluence_statistics(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get confluence statistics."""
    confluence_service = ConfluenceService(db)
    return await confluence_service.get_statistics(
        instrument=instrument, timeframe=timeframe,
    )
