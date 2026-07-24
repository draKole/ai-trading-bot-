"""Live Trading Persistence Service."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_, desc

from app.models.live_trading import (
    LiveTradingSession as SessionModel,
    LiveOrder as OrderModel,
    LiveExecution as ExecutionModel,
    BrokerConnectionLog as LogModel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class LiveTradingService:
    """Persistence service for live trading."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, config: dict) -> dict:
        import json as _json
        db_session = SessionModel(
            account_id=config.get("account_id", ""),
            broker=config.get("broker", "tradovate"),
            initial_balance=config.get("initial_balance", 100_000.0),
            balance=config.get("initial_balance", 100_000.0),
            buying_power=config.get("initial_balance", 100_000.0),
            config_json=_json.dumps(config),
        )
        self.session.add(db_session)
        await self.session.flush()
        return {"id": db_session.id, "account_id": db_session.account_id}

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
        return {"id": s.id, "account_id": s.account_id}

    async def get_session(self, session_id: int) -> dict | None:
        result = await self.session.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        s = result.scalar_one_or_none()
        if s is None:
            return None
        return {
            "id": s.id, "account_id": s.account_id, "broker": s.broker,
            "connection_state": s.connection_state,
            "balance": s.balance, "buying_power": s.buying_power,
            "realized_pnl": s.realized_pnl, "unrealized_pnl": s.unrealized_pnl,
            "config_json": s.config_json,
        }

    async def get_sessions(self, limit: int = 50) -> list[dict]:
        result = await self.session.execute(
            select(SessionModel).order_by(desc(SessionModel.created_at)).limit(limit)
        )
        return [
            {"id": s.id, "account_id": s.account_id, "broker": s.broker,
             "connection_state": s.connection_state, "balance": s.balance}
            for s in result.scalars().all()
        ]

    async def store_order(self, session_id: int, order: dict) -> int:
        db_order = OrderModel(
            session_id=session_id,
            broker_order_id=order.get("broker_order_id", ""),
            order_type=order.get("order_type", "market"),
            action=order.get("action", "buy"),
            instrument=order.get("instrument", ""),
            quantity=order.get("quantity", 1),
            limit_price=order.get("limit_price"),
            stop_price=order.get("stop_price"),
            status=order.get("status", "pending"),
            filled_qty=order.get("filled_qty", 0),
            avg_fill_price=order.get("avg_fill_price", 0),
        )
        self.session.add(db_order)
        await self.session.flush()
        return db_order.id

    async def get_orders(self, session_id: int, limit: int = 200) -> list[dict]:
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.session_id == session_id)
            .order_by(desc(OrderModel.created_at)).limit(limit)
        )
        return [
            {"id": o.id, "session_id": o.session_id, "broker_order_id": o.broker_order_id,
             "order_type": o.order_type, "action": o.action, "instrument": o.instrument,
             "quantity": o.quantity, "status": o.status, "filled_qty": o.filled_qty,
             "avg_fill_price": o.avg_fill_price}
            for o in result.scalars().all()
        ]

    async def store_execution(self, session_id: int, order_id: int,
                              execution: dict) -> int:
        db_exec = ExecutionModel(
            session_id=session_id, order_id=order_id,
            instrument=execution.get("instrument", ""),
            action=execution.get("action", ""),
            quantity=execution.get("quantity", 0),
            price=execution.get("price", 0),
            commission=execution.get("commission", 0),
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
             "instrument": e.instrument, "action": e.action,
             "quantity": e.quantity, "price": e.price}
            for e in result.scalars().all()
        ]

    async def log_connection_event(self, session_id: int, event_type: str,
                                   detail: str) -> int:
        db_log = LogModel(session_id=session_id, event_type=event_type, detail=detail)
        self.session.add(db_log)
        await self.session.flush()
        return db_log.id
