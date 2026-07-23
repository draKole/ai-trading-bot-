"""Trade Management API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.trade_management import (
    TradeManagementService, TradeManagementConfig,
    init_trade, process_bar, Bar,
)

router = APIRouter()


@router.get("/trades")
async def list_trades(
    instrument: str = Query(...),
    state: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List managed trades."""
    service = TradeManagementService(db)
    trades = await service.get_trades(instrument=instrument, state=state, limit=limit)
    return {
        "instrument": instrument.upper(),
        "count": len(trades),
        "trades": [
            {
                "trade_id": t.trade_id, "setup_id": t.setup_id,
                "direction": t.direction, "state": t.state,
                "entry": t.entry_price, "current_stop": t.current_stop,
                "current_r": round(t.current_r, 4),
                "peak_r": round(t.peak_r, 4),
            }
            for t in trades
        ],
    }


@router.get("/trades/{trade_id}")
async def get_trade(
    trade_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single managed trade with events."""
    service = TradeManagementService(db)
    trade = await service.get_trade(trade_id)
    if trade is None:
        raise HTTPException(404, f"Trade not found: {trade_id}")
    events = await service.get_events(trade_id=trade_id)
    return {
        "trade": {
            "trade_id": trade.trade_id, "setup_id": trade.setup_id,
            "instrument": trade.instrument, "direction": trade.direction,
            "state": trade.state,
            "entry_price": trade.entry_price,
            "initial_stop": trade.initial_stop,
            "current_stop": trade.current_stop,
            "position_size": trade.position_size,
            "position_remaining": trade.position_remaining,
            "target_1": trade.target_1, "target_2": trade.target_2,
            "target_3": trade.target_3,
            "target_1_hit": trade.target_1_hit,
            "target_2_hit": trade.target_2_hit,
            "target_3_hit": trade.target_3_hit,
            "current_r": round(trade.current_r, 4),
            "peak_r": round(trade.peak_r, 4),
            "breakeven_reached": trade.breakeven_reached,
            "trailing_active": trade.trailing_active,
        },
        "events": [
            {"event_type": e.event_type, "from_state": e.from_state,
             "to_state": e.to_state, "detail": e.detail,
             "r_multiple": e.r_multiple}
            for e in events
        ],
    }


@router.get("/events")
async def list_events(
    trade_id: Optional[str] = Query(None),
    limit: int = Query(500, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """List trade events."""
    service = TradeManagementService(db)
    events = await service.get_events(trade_id=trade_id, limit=limit)
    return {
        "count": len(events),
        "events": [
            {"trade_id": e.trade_id, "event_type": e.event_type,
             "from_state": e.from_state, "to_state": e.to_state,
             "detail": e.detail, "r_multiple": e.r_multiple}
            for e in events
        ],
    }


@router.post("/manage-dry-run")
async def manage_dry_run(
    entry_price: float = Query(6010.0),
    stop_price: float = Query(6000.0),
    direction: str = Query("bullish"),
    bars_json: str = Query("[6020,6015,6030,6040]"),
):
    """Simulate trade management through a series of closing prices."""
    from datetime import datetime, timedelta
    import json

    prices = json.loads(bars_json)

    setup = {
        "setup_id": "dry-run-001", "instrument": "ES",
        "direction": direction,
        "preferred_entry": entry_price, "stop_reference": stop_price,
        "target_1": entry_price + 20 if direction == "bullish" else entry_price - 20,
        "target_2": entry_price + 40 if direction == "bullish" else entry_price - 40,
        "target_3": entry_price + 60 if direction == "bullish" else entry_price - 60,
    }
    config = TradeManagementConfig()
    trade = init_trade(setup, config=config)

    t0 = datetime(2025, 6, 16, 9, 30)
    all_events = []

    for i, price in enumerate(prices):
        bar = Bar(timestamp=t0 + timedelta(minutes=i * 5),
                  open=price, high=price + 1, low=price - 1, close=price)
        evts = process_bar(trade, bar)
        all_events.extend([e.to_dict() for e in evts])
        if trade.state == "exited":
            break

    return {
        "trade": trade.to_dict(),
        "events": all_events,
        "final_state": trade.state,
    }


@router.get("/statistics")
async def get_trade_statistics(
    instrument: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get trade management statistics."""
    service = TradeManagementService(db)
    return await service.get_statistics(instrument=instrument)
