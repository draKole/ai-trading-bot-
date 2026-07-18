"""Liquidity API endpoints."""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.liquidity import (
    LiquidityService, LiquidityConfig,
    LiquidityEngine, SessionEngine, SessionConfig,
    LiquidityType, LiquidityEventType,
)
from app.services.market_data import MarketDataService

router = APIRouter()


# ─── Detection ───────────────────────────────────────────────

@router.post("/detect")
async def detect_liquidity(
    instrument: str = Query(..., description="Instrument symbol"),
    timeframe: str = Query(..., description="Timeframe"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    equal_tolerance_pct: float = Query(0.05, ge=0.01, le=1.0),
    approach_threshold_pct: float = Query(0.1, ge=0.01, le=5.0),
    db: AsyncSession = Depends(get_db),
):
    """Run liquidity detection on stored bars and persist."""
    md_service = MarketDataService(db)
    lq_service = LiquidityService(db)

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

    config = LiquidityConfig(
        equal_level_tolerance_pct=equal_tolerance_pct,
        approach_threshold_pct=approach_threshold_pct,
    )
    result = await lq_service.detect_and_store(
        instrument=instrument.upper(), timeframe=timeframe,
        instrument_id=inst.id, bars=bars, config=config,
    )
    return result


@router.post("/detect-dry-run")
async def detect_liquidity_dry_run(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Run detection and return levels/events without storing."""
    md_service = MarketDataService(db)

    bars = await md_service.get_bars(
        instrument=instrument.upper(), timeframe=timeframe,
        start=datetime.fromisoformat(start) if start else None,
        end=datetime.fromisoformat(end) if end else None,
        limit=100000,
    )
    if not bars:
        raise HTTPException(status_code=404, detail="No bars found")

    engine = LiquidityEngine()
    levels = engine.detect_levels(bars, None, instrument.upper())
    events = engine.detect_events(levels, bars)

    return {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "bars_analyzed": len(bars),
        "levels_found": len(levels),
        "levels": [
            {"type": l.level_type.value, "price": l.price, "session": l.session.value if l.session else None}
            for l in levels
        ],
        "events_found": len(events),
        "events": [
            {
                "type": e.event_type.value,
                "level_type": e.level.level_type.value,
                "level_price": e.level.price,
                "bar_index": e.bar_index,
                "direction": e.direction,
            }
            for e in events
        ],
    }


# ─── Query ───────────────────────────────────────────────────

@router.get("/levels")
async def get_active_levels(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    level_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Query active liquidity levels."""
    md_service = MarketDataService(db)
    lq_service = LiquidityService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    levels = await lq_service.get_active_levels(
        instrument_id=inst.id,
        timeframe=timeframe,
        level_type=level_type,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(levels),
        "levels": [
            {
                "id": l.id,
                "type": l.level_type,
                "price": l.price,
                "session": l.session,
                "is_active": l.is_active,
                "source_timestamp": l.source_timestamp.isoformat(),
            }
            for l in levels
        ],
    }


@router.get("/events")
async def get_liquidity_events(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    limit: int = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Query liquidity events."""
    md_service = MarketDataService(db)
    lq_service = LiquidityService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    events = await lq_service.get_events(
        instrument_id=inst.id, timeframe=timeframe,
        event_type=event_type,
        start=datetime.fromisoformat(start) if start else None,
        end=datetime.fromisoformat(end) if end else None,
        limit=limit,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "level_type": e.level_type,
                "level_price": e.level_price,
                "direction": e.direction,
                "bar_timestamp": e.bar_timestamp.isoformat(),
                "bar_close": e.bar_close,
            }
            for e in events
        ],
    }


@router.get("/sweeps")
async def get_sweeps(
    instrument: str = Query(...),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Query sweep events specifically."""
    md_service = MarketDataService(db)
    lq_service = LiquidityService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    events = await lq_service.get_sweeps(
        instrument_id=inst.id, timeframe=timeframe, limit=limit,
    )
    return {
        "instrument": instrument.upper(),
        "count": len(events),
        "sweeps": [
            {
                "id": e.id,
                "level_type": e.level_type,
                "level_price": e.level_price,
                "direction": e.direction,
                "bar_timestamp": e.bar_timestamp.isoformat(),
            }
            for e in events
        ],
    }


@router.get("/session-status")
async def get_session_status(
    instrument: str = Query(...),
    session: str = Query(..., description="asia, london, ny_am, ny_pm"),
    db: AsyncSession = Depends(get_db),
):
    """Get liquidity status for a session."""
    md_service = MarketDataService(db)
    lq_service = LiquidityService(db)

    inst = await md_service.get_instrument_by_symbol(instrument.upper())
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    if session not in ("asia", "london", "ny_am", "ny_pm"):
        raise HTTPException(status_code=400, detail="Invalid session")

    return await lq_service.get_session_status(inst.id, session)


@router.get("/session-history")
async def get_session_history(
    instrument: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get all session boundaries as configured."""
    from app.services.liquidity.session_engine import SessionEngine

    engine = SessionEngine()
    now = datetime.now(ZoneInfo("UTC"))
    boundaries = engine.get_session_boundaries(now)

    return {
        "instrument": instrument.upper(),
        "reference_time_utc": now.isoformat(),
        "timezone": engine.config.timezone,
        "sessions": {
            s.value: {
                "start_utc": b.start_utc.isoformat(),
                "end_utc": b.end_utc.isoformat(),
            }
            for s, b in boundaries.items()
        },
    }


@router.get("/event-types")
async def list_liquidity_event_types():
    """List all liquidity level and event types."""
    return {
        "level_types": [e.value for e in LiquidityType],
        "event_types": [e.value for e in LiquidityEventType],
    }
