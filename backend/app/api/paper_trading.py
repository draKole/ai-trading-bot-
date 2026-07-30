"""Paper Trading API endpoints — order management, positions, P&L, trade history."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.paper_trading import (
    PaperTradingService, PaperTradingController, PaperTradingConfig,
    PaperSession, PaperOrder, PaperPosition, PaperExecution,
    execute_market_order, execute_limit_order,
    compute_slippage, compute_commission,
    update_position_after_fill, compute_unrealized_pnl,
)

router = APIRouter()

# In-memory controller for order fill simulation
_controller = PaperTradingController()


# ─── Helpers ──────────────────────────────────────────────

def _order_to_dict(o) -> dict:
    """Serialize a DB PaperOrder or engine PaperOrder to dict."""
    if hasattr(o, '__table__'):
        return {
            "id": o.id, "session_id": o.session_id,
            "order_type": o.order_type, "side": o.side,
            "instrument": o.instrument, "quantity": o.quantity,
            "price": o.price, "stop_price": o.stop_price,
            "status": o.status, "filled_qty": o.filled_qty,
            "fill_price": o.fill_price, "slippage": o.slippage,
            "commission": o.commission,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
    # Engine dataclass
    return o.to_dict()


def _position_to_dict(p) -> dict:
    """Serialize a DB PaperPosition to dict."""
    return {
        "id": p.id, "session_id": p.session_id,
        "instrument": p.instrument, "direction": p.direction,
        "quantity": p.quantity, "avg_entry_price": p.avg_entry_price,
        "current_price": p.current_price,
        "unrealized_pnl": p.unrealized_pnl,
        "realized_pnl": p.realized_pnl,
        "status": p.status,
        "opened_at": p.opened_at.isoformat() if p.opened_at else None,
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
    }


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
    from uuid import uuid4

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
        "status": "stopped", "stopped_at": datetime.now(timezone.utc),
    })
    return {"session_id": session_id, "status": "stopped"}


# ─── Account Summary ───────────────────────────────────────

@router.get("/account/{session_id}")
async def account_summary(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get account summary: balance, P&L, buying power, margin."""
    service = PaperTradingService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")

    positions = await service.get_positions(session_id, status="open")
    total_unrealized = sum(p.get("unrealized_pnl", 0.0) for p in positions)
    total_realized = session.get("realized_pnl", 0.0)
    balance = session.get("balance", 0.0)
    initial = session.get("initial_balance", 0.0)

    return {
        "session_id": session_id,
        "account_id": session.get("account_id", ""),
        "name": session.get("name", ""),
        "balance": balance,
        "buying_power": session.get("buying_power", balance),
        "initial_balance": initial,
        "realized_pnl": total_realized,
        "unrealized_pnl": total_unrealized,
        "total_pnl": total_realized + total_unrealized,
        "total_return_pct": round(
            ((total_realized + total_unrealized + balance) / initial - 1) * 100, 2,
        ) if initial > 0 else 0.0,
        "open_positions_count": len(positions),
        "status": session.get("status", "stopped"),
    }


# ─── Orders ────────────────────────────────────────────────

@router.post("/orders/place")
async def place_order(
    session_id: int = Query(...),
    order_type: str = Query("market"),
    side: str = Query(...),
    instrument: str = Query(...),
    quantity: int = Query(..., ge=1),
    price: Optional[float] = Query(None),
    stop_price: Optional[float] = Query(None),
    current_price: Optional[float] = Query(None, description="Current market price for fills"),
    current_high: Optional[float] = Query(None),
    current_low: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Place a new paper trading order. Market orders fill immediately if current_price provided."""
    service = PaperTradingService(db)

    order_status = "pending"
    fill_price_val: float | None = None
    filled_qty = 0
    slippage_val = 0.0
    commission_val = 0.0

    # If market order with current price, simulate fill immediately
    if order_type == "market" and current_price is not None:
        from app.services.paper_trading.engine import compute_slippage, compute_commission

        tick_size = 0.25 if instrument == "MNQ" else (1.0 if instrument == "NQ" else 0.25)
        slip = compute_slippage("market", side, current_price, 1, tick_size)
        fill_price_val = round(current_price + slip, 2)
        commission_val = compute_commission(quantity, 2.50)
        slippage_val = slip
        order_status = "filled"
        filled_qty = quantity
    elif (order_type == "limit" or order_type == "stop") and current_price is not None:
        # Check if limit/stop order triggers
        hi = current_high if current_high is not None else current_price
        lo = current_low if current_low is not None else current_price
        if order_type == "limit":
            if side == "buy" and lo <= (price or 0):
                fill_price_val = price
                order_status = "filled"
                filled_qty = quantity
            elif side == "sell" and hi >= (price or 0):
                fill_price_val = price
                order_status = "filled"
                filled_qty = quantity
        elif order_type == "stop":
            if side == "buy" and hi >= (stop_price or 0):
                fill_price_val = hi
                order_status = "filled"
                filled_qty = quantity
            elif side == "sell" and lo <= (stop_price or 0):
                fill_price_val = lo
                order_status = "filled"
                filled_qty = quantity
        if order_status == "filled":
            commission_val = round(quantity * 2.50, 2)

    order_data = {
        "order_type": order_type, "side": side, "instrument": instrument,
        "quantity": quantity, "price": price, "stop_price": stop_price,
        "status": order_status, "filled_qty": filled_qty,
        "fill_price": fill_price_val,
        "slippage": slippage_val, "commission": commission_val,
    }
    order_id = await service.store_order(session_id, order_data)

    # If filled, record an execution
    if order_status == "filled" and fill_price_val is not None:
        await service.store_execution(session_id, order_id, {
            "instrument": instrument, "side": side,
            "quantity": quantity, "price": fill_price_val,
            "commission": commission_val, "slippage": slippage_val,
        })
        # Update session balance
        session = await service.get_session(session_id)
        if session:
            cost = fill_price_val * quantity + commission_val
            new_balance = session["balance"] - cost if side == "buy" else session["balance"] + fill_price_val * quantity - commission_val
            new_realized = new_balance - session.get("initial_balance", 0.0)
            await service.update_session(session_id, {
                "balance": round(new_balance, 2),
                "realized_pnl": round(new_realized, 2),
            })

    return {
        "order_id": order_id,
        "status": order_status,
        "fill_price": fill_price_val,
        "filled_qty": filled_qty,
        "slippage": slippage_val,
        "commission": commission_val,
    }


@router.get("/orders")
async def list_orders(
    session_id: int = Query(...),
    status: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List orders for a session, optionally filtered by status."""
    service = PaperTradingService(db)
    orders = await service.get_orders(session_id, limit=limit)
    if status:
        orders = [o for o in orders if o.get("status") == status]
    return {"count": len(orders), "orders": orders}


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending order."""
    service = PaperTradingService(db)
    updated = await service.update_order(order_id, {
        "status": "cancelled",
        "cancelled_at": datetime.now(timezone.utc),
    })
    if updated is None:
        raise HTTPException(404, f"Order not found: {order_id}")
    return {"order_id": order_id, "status": "cancelled"}


@router.patch("/orders/{order_id}")
async def modify_order(
    order_id: int,
    quantity: Optional[int] = Query(None, ge=1),
    price: Optional[float] = Query(None),
    stop_price: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Modify a pending order's price or quantity."""
    service = PaperTradingService(db)

    from app.models.paper_trading import PaperOrder as OrderModel
    from sqlalchemy import select
    result = await db.execute(select(OrderModel).where(OrderModel.id == order_id))
    o = result.scalar_one_or_none()
    if o is None:
        raise HTTPException(404, f"Order not found: {order_id}")
    if o.status != "pending":
        raise HTTPException(400, f"Cannot modify order with status: {o.status}")

    updates = {}
    if quantity is not None:
        updates["quantity"] = quantity
    if price is not None:
        updates["price"] = price
    if stop_price is not None:
        updates["stop_price"] = stop_price

    if not updates:
        raise HTTPException(400, "No modifications provided")

    updated = await service.update_order(order_id, updates)
    return {"order_id": order_id, **updates, "status": updated["status"]}


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


# ─── Executions / Trade History ────────────────────────────

@router.get("/trades")
async def list_trades(
    session_id: int = Query(...),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get trade history — completed (filled) orders as a digest."""
    service = PaperTradingService(db)
    orders = await service.get_orders(session_id, limit=limit)
    # Filter to filled/cancelled orders only
    trades = []
    for o in orders:
        if o.get("status") in ("filled", "cancelled"):
            trades.append({
                "id": o.get("id"),
                "instrument": o.get("instrument"),
                "side": o.get("side"),
                "order_type": o.get("order_type"),
                "quantity": o.get("quantity"),
                "filled_qty": o.get("filled_qty"),
                "price": o.get("price"),
                "fill_price": o.get("fill_price"),
                "status": o.get("status"),
                "commission": o.get("commission"),
                "slippage": o.get("slippage"),
            })
    return {"count": len(trades), "trades": trades}


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
    """Get paper trading statistics from the controller."""
    stats = _controller.get_statistics(account_id)
    return stats
