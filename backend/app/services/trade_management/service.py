"""Trade Management Service — persistence layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_

from app.models.trade_management import (
    ManagedTrade as TradeModel,
    TradeEvent as EventModel,
    TradeManagementRule as RuleModel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class TradeManagementService:
    """Service for trade management and persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def store_trade(self, trade: dict) -> dict:
        """Persist a managed trade and its events."""
        db_trade = TradeModel(
            trade_id=trade["trade_id"],
            setup_id=trade["setup_id"],
            instrument=trade["instrument"],
            direction=trade["direction"],
            entry_price=trade["entry_price"],
            initial_stop=trade["initial_stop"],
            current_stop=trade["current_stop"],
            position_size=trade["position_size"],
            position_remaining=trade["position_remaining"],
            target_1=trade.get("target_1"),
            target_2=trade.get("target_2"),
            target_3=trade.get("target_3"),
            target_1_hit=trade["target_1_hit"],
            target_2_hit=trade["target_2_hit"],
            target_3_hit=trade["target_3_hit"],
            state=trade["state"],
            initial_risk_r=trade["initial_risk_r"],
            peak_r=trade["peak_r"],
            max_adverse_r=trade["max_adverse_r"],
            current_r=trade["current_r"],
            breakeven_reached=trade["breakeven_reached"],
            trailing_active=trade["trailing_active"],
        )
        self.session.add(db_trade)
        await self.session.flush()
        return trade

    async def store_events(self, trade_id: str, events: list[dict]):
        for e in events:
            db_event = EventModel(
                trade_id=trade_id,
                event_type=e.get("event_type", ""),
                from_state=e.get("from_state", ""),
                to_state=e.get("to_state", ""),
                detail=e.get("detail", ""),
                price=e.get("price"),
                r_multiple=e.get("r_multiple", 0),
                position_remaining_pct=e.get("position_remaining_pct", 100),
            )
            self.session.add(db_event)
        await self.session.flush()

    async def get_trade(self, trade_id: str) -> TradeModel | None:
        result = await self.session.execute(
            select(TradeModel).where(TradeModel.trade_id == trade_id)
        )
        return result.scalar_one_or_none()

    async def get_trades(
        self, instrument: str, state: str | None = None, limit: int = 100,
    ) -> list[TradeModel]:
        conditions = [TradeModel.instrument == instrument.upper()]
        if state:
            conditions.append(TradeModel.state == state)
        result = await self.session.execute(
            select(TradeModel).where(and_(*conditions))
            .order_by(TradeModel.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_events(
        self, trade_id: str | None = None, limit: int = 500,
    ) -> list[EventModel]:
        conditions = []
        if trade_id:
            conditions.append(EventModel.trade_id == trade_id)
        query = select(EventModel).order_by(EventModel.created_at.desc()).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_rules(self, enabled_only: bool = True) -> list[RuleModel]:
        conditions = []
        if enabled_only:
            conditions.append(RuleModel.enabled == True)
        query = select(RuleModel).order_by(RuleModel.priority.desc())
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_statistics(self, instrument: str) -> dict:
        result = await self.session.execute(
            select(TradeModel).where(TradeModel.instrument == instrument.upper())
        )
        trades = list(result.scalars().all())
        total = len(trades)
        by_state = {}
        avg_r = 0.0
        exited = [t for t in trades if t.state == "exited"]
        for t in trades:
            by_state[t.state] = by_state.get(t.state, 0) + 1
        if exited:
            avg_r = sum(t.peak_r for t in exited) / len(exited)
        return {
            "instrument": instrument.upper(),
            "total_trades": total,
            "active_trades": by_state.get("active", 0),
            "exited_trades": len(exited),
            "by_state": by_state,
            "avg_peak_r": round(avg_r, 4),
        }
