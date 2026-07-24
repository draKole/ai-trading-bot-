"""Live Trading API endpoints."""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.broker.base import BrokerOrder
from app.services.live_trading import (
    LiveTradingService, LiveTradingController, LiveTradingConfig,
)
from app.services.broker.tradovate import TradovateAdapter

router = APIRouter()

_controller = LiveTradingController()


@router.get("/sessions")
async def list_sessions(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = LiveTradingService(db)
    sessions = await service.get_sessions(limit=limit)
    return {"count": len(sessions), "sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = LiveTradingService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")
    return session


@router.post("/connect")
async def connect_broker(
    account_id: str = Query(...),
    broker: str = Query("tradovate"),
    initial_balance: float = Query(100_000.0),
    db: AsyncSession = Depends(get_db),
):
    service = LiveTradingService(db)
    config = LiveTradingConfig(
        account_id=account_id, broker=broker,
        initial_balance=initial_balance,
    )
    adapter = TradovateAdapter(config.to_dict())
    session = _controller.create_session(config, adapter)
    ok = await _controller.connect(account_id)
    if not ok:
        raise HTTPException(500, "Failed to connect")

    await service.create_session(config.to_dict())
    return {"account_id": account_id, "status": "connected"}


@router.post("/disconnect")
async def disconnect_broker(
    account_id: str = Query(...),
):
    ok = await _controller.disconnect(account_id)
    return {"account_id": account_id, "status": "disconnected" if ok else "error"}


@router.post("/start")
async def start_session(
    account_id: str = Query(...),
    broker: str = Query("tradovate"),
    initial_balance: float = Query(100_000.0),
    db: AsyncSession = Depends(get_db),
):
    service = LiveTradingService(db)
    config = LiveTradingConfig(account_id=account_id, broker=broker,
                               initial_balance=initial_balance)
    adapter = TradovateAdapter(config.to_dict())
    _controller.create_session(config, adapter)
    await _controller.connect(account_id)
    await service.create_session(config.to_dict())
    return {"account_id": account_id, "status": "started"}


@router.post("/stop")
async def stop_session(
    account_id: str = Query(...),
):
    await _controller.disconnect(account_id)
    return {"account_id": account_id, "status": "stopped"}


@router.get("/status")
async def get_status(account_id: str = Query(...)):
    return _controller.get_statistics(account_id)


@router.post("/orders/place")
async def place_order(
    account_id: str = Query(...),
    action: str = Query(...),
    instrument: str = Query(...),
    quantity: int = Query(..., ge=1),
    order_type: str = Query("market"),
    limit_price: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = LiveTradingService(db)
    order = BrokerOrder(
        action=action, instrument=instrument, quantity=quantity,
        order_type=order_type, limit_price=limit_price,
    )
    result = await _controller.place_order(account_id, order)
    return result


@router.get("/orders")
async def list_orders(
    session_id: int = Query(...),
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
):
    service = LiveTradingService(db)
    orders = await service.get_orders(session_id, limit=limit)
    return {"count": len(orders), "orders": orders}


@router.get("/executions")
async def list_executions(
    session_id: int = Query(...),
    limit: int = Query(500, le=2000),
    db: AsyncSession = Depends(get_db),
):
    service = LiveTradingService(db)
    executions = await service.get_executions(session_id, limit=limit)
    return {"count": len(executions), "executions": executions}


@router.get("/positions")
async def get_positions(account_id: str = Query(...)):
    await _controller.sync_positions(account_id)
    session = _controller.get_session(account_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {account_id}")
    return {"account_id": account_id, "positions": [p.to_dict() for p in session.open_positions]}


@router.get("/account")
async def get_account(account_id: str = Query(...)):
    await _controller.sync_account(account_id)
    stats = _controller.get_statistics(account_id)
    return stats


@router.post("/emergency_stop")
async def emergency_stop(account_id: str = Query(...)):
    return _controller.emergency_stop(account_id)


@router.get("/statistics")
async def get_statistics(account_id: str = Query(...)):
    return _controller.get_statistics(account_id)
