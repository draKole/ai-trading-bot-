"""Audit Log Service — immutable append-only event recording.

Every order, fill, cancel, and modification is logged.
Records are immutable — no update or delete operations.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select, desc, func

from app.models.audit_log import TradingAuditLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AuditLogService:
    """Append-only audit log persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        event_type: str,
        *,
        client_order_id: Optional[str] = None,
        broker_order_id: Optional[str] = None,
        instrument: Optional[str] = None,
        side: Optional[str] = None,
        order_type: Optional[str] = None,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        fill_price: Optional[float] = None,
        commission: Optional[float] = None,
        reason: Optional[str] = None,
        mode: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        """Record an event to the immutable audit log. Returns new log ID."""
        entry = TradingAuditLog(
            event_type=event_type,
            client_order_id=client_order_id,
            broker_order_id=broker_order_id,
            instrument=instrument,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            fill_price=fill_price,
            commission=commission,
            reason=reason,
            mode=mode,
            metadata_json=metadata,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry.id

    async def query_logs(
        self,
        *,
        event_type: Optional[str] = None,
        client_order_id: Optional[str] = None,
        instrument: Optional[str] = None,
        mode: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Query audit logs with optional filters. Returns (entries, total_count)."""
        conditions = []
        if event_type:
            conditions.append(TradingAuditLog.event_type == event_type)
        if client_order_id:
            conditions.append(TradingAuditLog.client_order_id == client_order_id)
        if instrument:
            conditions.append(TradingAuditLog.instrument == instrument)
        if mode:
            conditions.append(TradingAuditLog.mode == mode)

        where_clause = conditions[0] if len(conditions) == 1 else None
        if len(conditions) > 1:
            from sqlalchemy import and_
            where_clause = and_(*conditions)

        # Total count
        count_query = select(func.count(TradingAuditLog.id))
        if where_clause is not None:
            count_query = count_query.where(where_clause)
        total = (await self.session.execute(count_query)).scalar_one()

        # Fetch page
        query = select(TradingAuditLog).order_by(desc(TradingAuditLog.created_at)).offset(offset).limit(limit)
        if where_clause is not None:
            query = query.where(where_clause)
        result = await self.session.execute(query)
        entries = [
            {
                "id": e.id, "event_type": e.event_type,
                "client_order_id": e.client_order_id,
                "broker_order_id": e.broker_order_id,
                "instrument": e.instrument, "side": e.side,
                "order_type": e.order_type, "quantity": e.quantity,
                "price": e.price, "fill_price": e.fill_price,
                "commission": e.commission, "reason": e.reason,
                "mode": e.mode,
                "metadata": e.metadata_json,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in result.scalars().all()
        ]
        return entries, total
