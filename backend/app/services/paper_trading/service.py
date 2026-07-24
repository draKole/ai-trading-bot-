"""Paper Trading Persistence Service — CRUD for sessions, orders, positions, executions."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_, desc

from app.models.paper_trading import (
    PaperTradingSession as SessionModel,
    PaperOrder as OrderModel,
    PaperPosition as PositionModel,
    PaperExecution as ExecutionModel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class PaperTradingService:
    """Persistence service for paper trading."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Sessions ──────────────────────────────────────────

    async def create_session(self, config: dict) -> dict:
        import json as _json
        db_session = SessionModel(
            account_id=config.get("account_id", ""),
            name=config.get("name", "Default"),
            balance=config.get("initial_balance", 100_000.0),
            buying_power=config.get("initial_balance", 100_000.0),
            initial_balance=config.get("initial_balance", 100_000.0),
            status="stopped",
            config_json=_json.dumps(config),
        )
        self.session.add(db_session)
        await self.session.flush()
        return {"id": db_session.id, "account_id": db_session.account_id, "status": db_session.status}

    async def update_session(self, session_id: int, updates: dict) -> dict | None:
        result = await self.session.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        s = result.scalar_one_or_none()
        if s is None:
            return None
        for k, v in updates.items():
            if hasattr(s, k):
                setattr(s, k, v)
        await self.session.flush()
        return {"id": s.id, "account_id": s.account_id, "status": s.status}

    async def get_session(self, session_id: int) -> dict | None:
        result = await self.session.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        s = result.scalar_one_or_none()
        if s is None:
            return None
        return self._session_to_dict(s)

    async def get_sessions(self, status: str | None = None, limit: int = 50) -> list[dict]:
        conditions = []
        if status:
            conditions.append(SessionModel.status == status)
        query = select(SessionModel).order_by(desc(SessionModel.created_at)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return [self._session_to_dict(s) for s in result.scalars().all()]

    def _session_to_dict(self, s: SessionModel) -> dict:
        return {
            "id": s.id, "account_id": s.account_id, "name": s.name,
            "balance": s.balance, "buying_power": s.buying_power,
            "initial_balance": s.initial_balance,
            "realized_pnl": s.realized_pnl, "unrealized_pnl": s.unrealized_pnl,
            "status": s.status, "config_json": s.config_json,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }

    # ── Orders ────────────────────────────────────────────

    async def store_order(self, session_id: int, order: dict) -> int:
        db_order = OrderModel(
            session_id=session_id,
            order_type=order.get("order_type", "market"),
            side=order.get("side", "buy"),
            instrument=order.get("instrument", ""),
            quantity=order.get("quantity", 1),
            price=order.get("price"),
            stop_price=order.get("stop_price"),
            status=order.get("status", "pending"),
            filled_qty=order.get("filled_qty", 0),
            fill_price=order.get("fill_price"),
            slippage=order.get("slippage", 0),
            commission=order.get("commission", 0),
        )
        self.session.add(db_order)
        await self.session.flush()
        return db_order.id

    async def update_order(self, order_id: int, updates: dict) -> dict | None:
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.id == order_id)
        )
        o = result.scalar_one_or_none()
        if o is None:
            return None
        for k, v in updates.items():
            if hasattr(o, k):
                setattr(o, k, v)
        await self.session.flush()
        return {"id": o.id, "status": o.status}

    async def get_orders(self, session_id: int, limit: int = 200) -> list[dict]:
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.session_id == session_id)
            .order_by(desc(OrderModel.created_at)).limit(limit)
        )
        return [
            {"id": o.id, "session_id": o.session_id, "order_type": o.order_type,
             "side": o.side, "instrument": o.instrument, "quantity": o.quantity,
             "price": o.price, "status": o.status, "filled_qty": o.filled_qty,
             "fill_price": o.fill_price, "slippage": o.slippage,
             "commission": o.commission}
            for o in result.scalars().all()
        ]

    # ── Positions ─────────────────────────────────────────

    async def store_position(self, session_id: int, pos: dict) -> int:
        db_pos = PositionModel(
            session_id=session_id,
            instrument=pos.get("instrument", ""),
            direction=pos.get("direction", "long"),
            quantity=pos.get("quantity", 0),
            avg_entry_price=pos.get("avg_entry_price", 0),
            current_price=pos.get("current_price", 0),
            unrealized_pnl=pos.get("unrealized_pnl", 0),
            realized_pnl=pos.get("realized_pnl", 0),
            status=pos.get("status", "open"),
        )
        self.session.add(db_pos)
        await self.session.flush()
        return db_pos.id

    async def get_positions(self, session_id: int, status: str | None = None,
                            limit: int = 100) -> list[dict]:
        conditions = [PositionModel.session_id == session_id]
        if status:
            conditions.append(PositionModel.status == status)
        result = await self.session.execute(
            select(PositionModel).where(and_(*conditions))
            .order_by(desc(PositionModel.created_at)).limit(limit)
        )
        return [
            {"id": p.id, "session_id": p.session_id, "instrument": p.instrument,
             "direction": p.direction, "quantity": p.quantity,
             "avg_entry_price": p.avg_entry_price, "current_price": p.current_price,
             "unrealized_pnl": p.unrealized_pnl, "realized_pnl": p.realized_pnl,
             "status": p.status,
             "opened_at": p.opened_at.isoformat() if p.opened_at else None}
            for p in result.scalars().all()
        ]

    # ── Executions ────────────────────────────────────────

    async def store_execution(self, session_id: int, order_id: int,
                              execution: dict) -> int:
        db_exec = ExecutionModel(
            session_id=session_id, order_id=order_id,
            instrument=execution.get("instrument", ""),
            side=execution.get("side", ""),
            quantity=execution.get("quantity", 0),
            price=execution.get("price", 0),
            commission=execution.get("commission", 0),
            slippage=execution.get("slippage", 0),
        )
        self.session.add(db_exec)
        await self.session.flush()
        return db_exec.id

    async def get_executions(self, session_id: int, limit: int = 500) -> list[dict]:
        result = await self.session.execute(
            select(ExecutionModel).where(ExecutionModel.session_id == session_id)
            .order_by(desc(ExecutionModel.created_at)).limit(limit)
        )
        return [
            {"id": e.id, "session_id": e.session_id, "order_id": e.order_id,
             "instrument": e.instrument, "side": e.side,
             "quantity": e.quantity, "price": e.price,
             "commission": e.commission, "slippage": e.slippage}
            for e in result.scalars().all()
        ]
