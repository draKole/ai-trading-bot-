"""SMT API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.smt import SMTService, SMTConfig, detect_smt_divergence, SMTDirection
from app.services.market_data import MarketDataService
from app.services.market_structure.service import MarketStructureService

router = APIRouter()

# ─── Pairs ───────────────────────────────────────────────────

@router.get("/pairs")
async def get_supported_pairs(db: AsyncSession = Depends(get_db)):
    """Get supported SMT instrument pairs."""
    smt_service = SMTService(db)
    configs = await smt_service.get_pair_configs()
    return {
        "pairs": [
            {
                "id": c.id,
                "primary": c.primary_instrument,
                "secondary": c.secondary_instrument,
                "enabled": c.enabled,
                "tolerance_s": c.timestamp_tolerance_seconds,
                "min_div_pct": c.min_divergence_pct,
                "timeframes": c.enabled_timeframes,
                "label": c.label,
            }
            for c in configs
        ],
    }


# ─── Detection ───────────────────────────────────────────────

@router.post("/detect")
async def detect_smt(
    primary: str = Query(..., description="Primary instrument"),
    secondary: str = Query(..., description="Secondary instrument"),
    timeframe: str = Query(...),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    tolerance_seconds: float = Query(300.0, ge=0),
    min_divergence_pct: float = Query(0.05, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Run SMT divergence detection between two instruments and store results."""
    md_service = MarketDataService(db)
    ms_service = MarketStructureService(db)
    smt_service = SMTService(db)

    # Get instrument IDs
    inst_p = await md_service.get_instrument_by_symbol(primary.upper())
    if inst_p is None:
        raise HTTPException(404, f"Instrument not found: {primary}")

    inst_s = await md_service.get_instrument_by_symbol(secondary.upper())
    if inst_s is None:
        raise HTTPException(404, f"Instrument not found: {secondary}")

    # Get MS events for both
    p_events = await ms_service.get_events(
        instrument_id=inst_p.id, timeframe=timeframe, limit=10000,
    )
    p_swings = [
        {"swing_type": e.event_type, "price": e.price_level,
         "bar_index": e.bar_index, "timestamp": e.bar_timestamp,
         "id": e.id, "prior_price": e.parent_swing_id}
        for e in (p_events or [])
    ]

    s_events = await ms_service.get_events(
        instrument_id=inst_s.id, timeframe=timeframe, limit=10000,
    )
    s_swings = [
        {"swing_type": e.event_type, "price": e.price_level,
         "bar_index": e.bar_index, "timestamp": e.bar_timestamp,
         "id": e.id, "prior_price": e.parent_swing_id}
        for e in (s_events or [])
    ]

    config = SMTConfig(
        timestamp_tolerance_seconds=tolerance_seconds,
        min_divergence_pct=min_divergence_pct,
    )
    result = await smt_service.detect_and_store(
        primary_instrument=primary.upper(),
        secondary_instrument=secondary.upper(),
        timeframe=timeframe,
        primary_swings=p_swings,
        secondary_swings=s_swings,
        config=config,
    )
    return result


@router.post("/detect-dry-run")
async def detect_smt_dry_run(
    primary: str = Query(...),
    secondary: str = Query(...),
    timeframe: str = Query(...),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    tolerance_seconds: float = Query(300.0, ge=0),
    min_divergence_pct: float = Query(0.05, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Run SMT detection without storing."""
    md_service = MarketDataService(db)
    ms_service = MarketStructureService(db)

    inst_p = await md_service.get_instrument_by_symbol(primary.upper())
    if inst_p is None:
        raise HTTPException(404, f"Instrument not found: {primary}")
    inst_s = await md_service.get_instrument_by_symbol(secondary.upper())
    if inst_s is None:
        raise HTTPException(404, f"Instrument not found: {secondary}")

    p_events = await ms_service.get_events(
        instrument_id=inst_p.id, timeframe=timeframe, limit=10000,
    )
    p_swings = [
        {"swing_type": e.event_type, "price": e.price_level,
         "bar_index": e.bar_index, "timestamp": e.bar_timestamp,
         "id": e.id, "prior_price": e.parent_swing_id}
        for e in (p_events or [])
    ]

    s_events = await ms_service.get_events(
        instrument_id=inst_s.id, timeframe=timeframe, limit=10000,
    )
    s_swings = [
        {"swing_type": e.event_type, "price": e.price_level,
         "bar_index": e.bar_index, "timestamp": e.bar_timestamp,
         "id": e.id, "prior_price": e.parent_swing_id}
        for e in (s_events or [])
    ]

    config = SMTConfig(
        timestamp_tolerance_seconds=tolerance_seconds,
        min_divergence_pct=min_divergence_pct,
    )
    events = detect_smt_divergence(
        primary_swings=p_swings, secondary_swings=s_swings,
        primary_instrument=primary.upper(), secondary_instrument=secondary.upper(),
        timeframe=timeframe, config=config,
    )

    return {
        "pair": f"{primary.upper()}/{secondary.upper()}",
        "timeframe": timeframe,
        "events_found": len(events),
        "events": [
            {
                "direction": e.direction,
                "p_price": e.primary_swing_price,
                "s_price": e.secondary_swing_price,
                "div_pct": round(e.divergence_pct, 4),
                "delta_s": round(e.timestamp_delta_seconds, 1),
            }
            for e in events
        ],
    }


# ─── Query ───────────────────────────────────────────────────

@router.get("/events")
async def get_smt_events(
    primary: Optional[str] = Query(None),
    secondary: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    limit: int = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Query SMT divergence events."""
    smt_service = SMTService(db)
    events = await smt_service.get_events(
        primary_instrument=primary, secondary_instrument=secondary,
        timeframe=timeframe, direction=direction, limit=limit,
    )
    return {
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "pair": f"{e.primary_instrument}/{e.secondary_instrument}",
                "direction": e.direction,
                "timeframe": e.timeframe,
                "p_price": e.primary_swing_price,
                "s_price": e.secondary_swing_price,
                "div_pct": round(e.divergence_pct, 4),
                "detected": e.detection_timestamp.isoformat(),
            }
            for e in events
        ],
    }


@router.get("/latest")
async def get_latest_smt(
    primary: str = Query(...),
    secondary: str = Query(...),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(10, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get latest SMT signals for a pair."""
    smt_service = SMTService(db)
    events = await smt_service.get_latest(
        primary_instrument=primary, secondary_instrument=secondary,
        timeframe=timeframe, limit=limit,
    )
    return {
        "pair": f"{primary.upper()}/{secondary.upper()}",
        "count": len(events),
        "signals": [
            {
                "id": e.id,
                "direction": e.direction,
                "timeframe": e.timeframe,
                "div_pct": round(e.divergence_pct, 4),
                "detected": e.detection_timestamp.isoformat(),
            }
            for e in events
        ],
    }


@router.get("/statistics")
async def get_smt_statistics(
    primary: Optional[str] = Query(None),
    secondary: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get SMT statistics."""
    smt_service = SMTService(db)
    return await smt_service.get_statistics(
        primary_instrument=primary, secondary_instrument=secondary,
        timeframe=timeframe,
    )


@router.get("/directions")
async def list_directions():
    return {"directions": [e.value for e in SMTDirection]}
