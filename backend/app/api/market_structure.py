"""Market Structure API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.market_structure import (
    MarketStructureService,
    MarketStructureConfig,
    MarketStructureEngine,
    StructureEventType,
)
from app.services.market_data import MarketDataService

router = APIRouter()


# ─── Detection ───────────────────────────────────────────────

@router.post("/detect")
async def detect_structure(
    instrument: str = Query(..., description="Instrument symbol"),
    timeframe: str = Query(..., description="Timeframe"),
    lookback: int = Query(5, ge=2, le=50),
    confirmation_bars: int = Query(1, ge=0, le=10),
    min_distance: int = Query(3, ge=1, le=20),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Run market structure detection on stored bars and persist events."""
    md_service = MarketDataService(db)
    ms_service = MarketStructureService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Instrument not found: {instrument}")

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    bars = await md_service.get_bars(
        instrument=instrument.upper(),
        timeframe=timeframe,
        start=start_dt,
        end=end_dt,
        limit=100000,
    )

    if not bars:
        raise HTTPException(
            status_code=404,
            detail=f"No bars found for {instrument} {timeframe}",
        )

    config = MarketStructureConfig(
        swing_lookback=lookback,
        swing_confirmation_bars=confirmation_bars,
        min_structure_distance_bars=min_distance,
    )

    result = await ms_service.detect_and_store(
        instrument=instrument.upper(),
        timeframe=timeframe,
        instrument_id=inst.id,
        bars=bars,
        config=config,
    )

    return result


@router.post("/detect-dry-run")
async def detect_structure_dry_run(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    lookback: int = Query(5, ge=2, le=50),
    confirmation_bars: int = Query(1, ge=0, le=10),
    min_distance: int = Query(3, ge=1, le=20),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Run detection and return events without storing them."""
    md_service = MarketDataService(db)

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    bars = await md_service.get_bars(
        instrument=instrument.upper(),
        timeframe=timeframe,
        start=start_dt,
        end=end_dt,
        limit=100000,
    )

    if not bars:
        raise HTTPException(status_code=404, detail="No bars found")

    config = MarketStructureConfig(
        swing_lookback=lookback,
        swing_confirmation_bars=confirmation_bars,
        min_structure_distance_bars=min_distance,
    )

    engine = MarketStructureEngine(config)
    events = engine.analyze_from_ohlcv(bars, instrument.upper(), timeframe)

    return {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "bars_analyzed": len(bars),
        "events_found": len(events),
        "config": config.to_dict(),
        "events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type.value,
                "price_level": e.price_level,
                "direction": e.direction,
                "bar_index": e.bar_index,
            }
            for e in events
        ],
    }


# ─── Query ───────────────────────────────────────────────────

@router.get("/events")
async def get_events(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    limit: int = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Query stored market structure events."""
    md_service = MarketDataService(db)
    ms_service = MarketStructureService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    events = await ms_service.get_events(
        instrument_id=inst.id,
        timeframe=timeframe,
        event_type=event_type,
        start=start_dt,
        end=end_dt,
        limit=limit,
    )

    return {
        "instrument": instrument.upper(),
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "timestamp": e.bar_timestamp.isoformat(),
                "event_type": e.event_type,
                "price_level": e.price_level,
                "direction": e.direction,
                "timeframe": e.timeframe,
            }
            for e in events
        ],
    }


@router.get("/latest")
async def get_latest_structure(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest market structure summary."""
    md_service = MarketDataService(db)
    ms_service = MarketStructureService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    return await ms_service.get_latest_structure(
        instrument_id=inst.id,
        timeframe=timeframe,
    )


@router.get("/event-types")
async def list_event_types():
    """List all structure event types."""
    return {"event_types": [e.value for e in StructureEventType]}
