"""FVG API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.fvg import FVGService, FVGConfig, detect_fvgs, apply_lifecycle, FVGDirection, FVGStatus
from app.services.market_data import MarketDataService

router = APIRouter()


# ─── Detection ───────────────────────────────────────────────

@router.post("/detect")
async def detect_fvgs_endpoint(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    min_gap_size: float = Query(0.0, ge=0),
    min_gap_pct: float = Query(0.01, ge=0, le=100),
    fill_tolerance_pct: float = Query(1.0, ge=0, le=100),
    use_close_for_fill: bool = Query(False),
    invalidation_pct: float = Query(0.5, ge=0, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Run FVG detection and persist results."""
    md_service = MarketDataService(db)
    fvg_service = FVGService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Instrument not found: {instrument}")

    bars = await md_service.get_bars(
        instrument=instrument.upper(), timeframe=timeframe,
        start=datetime.fromisoformat(start) if start else None,
        end=datetime.fromisoformat(end) if end else None,
        limit=100000,
    )
    if not bars:
        raise HTTPException(status_code=404, detail="No bars found")

    config = FVGConfig(
        min_gap_size=min_gap_size,
        min_gap_size_pct=min_gap_pct,
        fill_tolerance_pct=fill_tolerance_pct,
        use_close_for_fill=use_close_for_fill,
        invalidation_pct=invalidation_pct,
    )
    result = await fvg_service.detect_and_store(
        instrument=instrument.upper(), timeframe=timeframe,
        instrument_id=inst.id, bars=bars, config=config,
    )
    return result


@router.post("/detect-dry-run")
async def detect_fvgs_dry_run(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Run detection and return results without storing."""
    md_service = MarketDataService(db)

    bars = await md_service.get_bars(
        instrument=instrument.upper(), timeframe=timeframe,
        start=datetime.fromisoformat(start) if start else None,
        end=datetime.fromisoformat(end) if end else None,
        limit=100000,
    )
    if not bars:
        raise HTTPException(status_code=404, detail="No bars found")

    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    closes = [b.close for b in bars]
    timestamps = [b.timestamp for b in bars]

    fvgs = detect_fvgs(highs, lows, closes, timestamps, instrument.upper(), timeframe)
    fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, timestamps)

    return {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "bars_analyzed": len(bars),
        "fvgs_found": len(fvgs),
        "fvgs": [
            {
                "direction": f.direction,
                "upper": f.upper_bound,
                "lower": f.lower_bound,
                "midpoint": f.midpoint,
                "gap_size_pct": round(f.gap_size_pct, 4),
                "status": f.status,
                "fill_pct": round(f.fill_percentage, 1),
                "creation_bar": f.creation_bar_index,
            }
            for f in fvgs
        ],
        "events_found": len(events),
        "events": [
            {
                "type": e.event_type,
                "bar_index": e.bar_index,
                "fill_pct": round(e.fill_percentage, 1),
            }
            for e in events
        ],
    }


# ─── Query ───────────────────────────────────────────────────

@router.get("/active")
async def get_active_fvgs(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Query FVGs (defaults to active/partially_filled)."""
    md_service = MarketDataService(db)
    fvg_service = FVGService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    fvgs = await fvg_service.get_active_fvgs(
        instrument_id=inst.id, timeframe=timeframe,
        direction=direction, status=status,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(fvgs),
        "fvgs": [
            {
                "id": f.id,
                "direction": f.direction,
                "timeframe": f.timeframe,
                "upper": f.upper_bound,
                "lower": f.lower_bound,
                "midpoint": f.midpoint,
                "gap_size_pct": round(f.gap_size_pct, 4),
                "status": f.status,
                "fill_pct": round(f.fill_percentage, 1),
                "created": f.creation_timestamp.isoformat(),
            }
            for f in fvgs
        ],
    }


@router.get("/events")
async def get_fvg_events(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Query FVG lifecycle events."""
    md_service = MarketDataService(db)
    fvg_service = FVGService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    events = await fvg_service.get_fvg_events(
        instrument_id=inst.id, timeframe=timeframe,
        event_type=event_type, limit=limit,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "fvg_id": e.fvg_id,
                "event_type": e.event_type,
                "direction": e.fvg_direction,
                "fill_pct": round(e.fill_percentage, 1),
                "timestamp": e.bar_timestamp.isoformat(),
            }
            for e in events
        ],
    }


@router.get("/statistics")
async def get_fvg_statistics(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get FVG statistics grouped by timeframe."""
    md_service = MarketDataService(db)
    fvg_service = FVGService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    return await fvg_service.get_fvg_statistics(
        instrument_id=inst.id, timeframe=timeframe,
    )


@router.get("/directions")
async def list_directions():
    """List FVG direction values."""
    return {"directions": [e.value for e in FVGDirection]}


@router.get("/statuses")
async def list_statuses():
    """List FVG status values."""
    return {"statuses": [e.value for e in FVGStatus]}
