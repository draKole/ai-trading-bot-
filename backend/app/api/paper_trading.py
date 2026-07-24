"""Paper Trading API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.paper_trading import (
    PaperTradingService, PaperTradingController, PaperTradingConfig,
    PaperSession,
)

router = APIRouter()

# In-memory controller for simplicity — in production this would be persisted/recovered
_controller = PaperTradingController()


# ─── Sessions ──────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List paper trading sessions."""
    service = PaperTradingService(db)
    sessions = await service.get_sessions(status=status, limit=limit)
    return {"count": len(sessions), "sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a paper trading session."""
    service = PaperTradingService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")
    return session


@router.post("/start")
async def start_session(
    name: str = Query("Default Paper Account"),
    initial_balance: float = Query(100_000.0),
    db: AsyncSession = Depends(get_db),
):
    """Create and start a new paper trading session."""
    service = PaperTradingService(db)
    account_id = str(uuid4())

    config = PaperTradingConfig(
        account_id=account_id, name=name,
        initial_balance=initial_balance,
    )
    sess = _controller.create_session(config)
    _controller.start_session(account_id)

    db_session = await service.create_session({
        "account_id": account_id, "name": name,
        "initial_balance": initial_balance,
    })

    return {
        "session_id": db_session["id"],
        "account_id": account_id,
        "name": name,
        "balance": initial_balance,
        "status": "running",
    }


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Stop a paper trading session."""
    service = PaperTradingService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")

    await service.update_session(session_id, {
        "status": "stopped",
        "stopped_at": datetime.now(timezone.utc),
    })
    return {"session_id": session_id, "status": "stopped"}


@router.post("/sessions/{session_id}/pause")
async def pause_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Pause a paper trading session."""
    service = PaperTradingService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")
    await service.update_session(session_id, {"status": "paused"})
    return {"session_id": session_id, "status": "paused"}


@router.post("/sessions/{session_id}/resume")
async def resume_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused paper trading session."""
    service = PaperTradingService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")
    if session["status"] != "paused":
        raise HTTPException(400, "Session is not paused")
    await service.update_session(session_id, {"status": "running"})
    return {"session_id": session_id, "status": "running"}


# ─── Orders ────────────────────────────────────────────────

@router.post("/orders/place")
async def place_order(
    session_id: int = Query(...),
    order_type: str = Query("market"),
    side: str = Query(...),
    instrument: str = Query(...),
    quantity: int = Query(..., ge=1),
    price: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Place a new order."""
    service = PaperTradingService(db)
    order = {
        "order_type": order_type, "side": side, "instrument": instrument,
        "quantity": quantity, "price": price,
        "status": "pending", "filled_qty": 0,
    }
    order_id = await service.store_order(session_id, order)
    return {"order_id": order_id, "status": "pending"}


@router.get("/orders")
async def list_orders(
    session_id: int = Query(...),
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List orders for a session."""
    service = PaperTradingService(db)
    orders = await service.get_orders(session_id, limit=limit)
    return {"count": len(orders), "orders": orders}


# ─── Positions ─────────────────────────────────────────────

@router.get("/positions")
async def list_positions(
    session_id: int = Query(...),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List positions for a session."""
    service = PaperTradingService(db)
    positions = await service.get_positions(session_id, status=status, limit=limit)
    return {"count": len(positions), "positions": positions}


# ─── Executions ────────────────────────────────────────────

@router.get("/executions")
async def list_executions(
    session_id: int = Query(...),
    limit: int = Query(500, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """List executions for a session."""
    service = PaperTradingService(db)
    executions = await service.get_executions(session_id, limit=limit)
    return {"count": len(executions), "executions": executions}


# ─── Statistics ────────────────────────────────────────────

@router.get("/statistics")
async def get_statistics(
    account_id: str = Query(...),
):
    """Get paper trading statistics."""
    stats = _controller.get_statistics(account_id)
    return stats
