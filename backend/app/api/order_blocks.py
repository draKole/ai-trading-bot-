"""Order Block API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.order_block import (
    OrderBlockService, OBConfig, detect_order_blocks, apply_ob_lifecycle,
    OBDirection, OBStatus,
)
from app.services.market_data import MarketDataService
from app.services.market_structure.service import MarketStructureService

router = APIRouter()


@router.post("/detect")
async def detect_obs_endpoint(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    lookback_bars: int = Query(5, ge=1, le=50),
    require_bos_choch: bool = Query(True),
    mitigation_method: str = Query("close"),
    mitigation_threshold_pct: float = Query(100.0, ge=0, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Run Order Block detection and persist results."""
    md_service = MarketDataService(db)
    ob_service = OrderBlockService(db)

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

    # Fetch Market Structure events for BOS/CHoCH triggers
    ms_service = MarketStructureService(db)
    ms_events = await ms_service.get_events(
        instrument_id=inst.id, timeframe=timeframe, limit=10000,
    )
    ms_event_dicts = [
        {"bar_index": e.bar_index, "event_type": e.event_type,
         "direction": e.direction, "id": e.id}
        for e in ms_events
    ] if ms_events else []

    config = OBConfig(
        lookback_bars=lookback_bars,
        require_bos_choch=require_bos_choch,
        mitigation_method=mitigation_method,
        mitigation_threshold_pct=mitigation_threshold_pct,
    )
    result = await ob_service.detect_and_store(
        instrument=instrument.upper(), timeframe=timeframe,
        instrument_id=inst.id, bars=bars, ms_events=ms_event_dicts, config=config,
    )
    return result


@router.post("/detect-dry-run")
async def detect_obs_dry_run(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Run detection and return results without storing."""
    md_service = MarketDataService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    bars = await md_service.get_bars(
        instrument=instrument.upper(), timeframe=timeframe,
        start=datetime.fromisoformat(start) if start else None,
        end=datetime.fromisoformat(end) if end else None,
        limit=100000,
    )
    if not bars:
        raise HTTPException(status_code=404, detail="No bars found")

    # Get MS events
    ms_service = MarketStructureService(db)
    ms_events = await ms_service.get_events(
        instrument_id=inst.id, timeframe=timeframe, limit=10000,
    )
    ms_event_dicts = [
        {"bar_index": e.bar_index, "event_type": e.event_type,
         "direction": e.direction, "id": e.id}
        for e in ms_events
    ] if ms_events else []

    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    opens = [b.open for b in bars]
    closes = [b.close for b in bars]
    volumes = [getattr(b, 'volume', 0) for b in bars]
    timestamps = [b.timestamp for b in bars]

    obs = detect_order_blocks(
        highs, lows, opens, closes, volumes, timestamps,
        ms_event_dicts, instrument.upper(), timeframe,
    )
    obs, events = apply_ob_lifecycle(obs, highs, lows, closes, timestamps)

    return {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "bars_analyzed": len(bars),
        "ms_events": len(ms_event_dicts),
        "obs_found": len(obs),
        "obs": [
            {
                "direction": o.direction,
                "upper": o.upper_bound,
                "lower": o.lower_bound,
                "status": o.status,
                "mit_pct": round(o.mitigation_percentage, 1),
                "origin_candle": o.origin_candle_index,
            }
            for o in obs
        ],
        "events_found": len(events),
    }


@router.get("/active")
async def get_active_obs(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Query Order Blocks (default: active/touched/partially_mitigated)."""
    md_service = MarketDataService(db)
    ob_service = OrderBlockService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    obs = await ob_service.get_active_obs(
        instrument_id=inst.id, timeframe=timeframe,
        direction=direction, status=status,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(obs),
        "obs": [
            {
                "id": o.id,
                "direction": o.direction,
                "timeframe": o.timeframe,
                "upper": o.upper_bound,
                "lower": o.lower_bound,
                "status": o.status,
                "mit_pct": round(o.mitigation_percentage, 1),
                "ms_event_id": o.related_ms_event_id,
                "created": o.creation_timestamp.isoformat(),
            }
            for o in obs
        ],
    }


@router.get("/events")
async def get_ob_events(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Query OB lifecycle events."""
    md_service = MarketDataService(db)
    ob_service = OrderBlockService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    events = await ob_service.get_ob_events(
        instrument_id=inst.id, timeframe=timeframe,
        event_type=event_type, limit=limit,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "ob_id": e.ob_id,
                "event_type": e.event_type,
                "direction": e.ob_direction,
                "mit_pct": round(e.mitigation_percentage, 1),
                "timestamp": e.bar_timestamp.isoformat(),
            }
            for e in events
        ],
    }


@router.get("/statistics")
async def get_ob_statistics(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get OB statistics grouped by timeframe."""
    md_service = MarketDataService(db)
    ob_service = OrderBlockService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    return await ob_service.get_ob_statistics(
        instrument_id=inst.id, timeframe=timeframe,
    )


@router.get("/directions")
async def list_directions():
    return {"directions": [e.value for e in OBDirection]}


@router.get("/statuses")
async def list_statuses():
    return {"statuses": [e.value for e in OBStatus]}
