"""Portfolio Service — persistence for portfolios, accounts, positions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_, desc

from app.models.portfolio import (
    Portfolio, PortfolioAccount, AllocationRule,
    PortfolioPosition, PortfolioStatistic,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class PortfolioService:
    """Persistence service for portfolio management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_portfolio(self, name: str, description: str = "",
                               total_capital: float = 0.0) -> dict:
        p = Portfolio(name=name, description=description,
                      total_capital=total_capital)
        self.session.add(p)
        await self.session.flush()
        return {"id": p.id, "name": p.name}

    async def get_portfolio(self, portfolio_id: int) -> dict | None:
        result = await self.session.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id)
        )
        p = result.scalar_one_or_none()
        if p is None:
            return None
        return {"id": p.id, "name": p.name, "description": p.description,
                "total_capital": p.total_capital, "allocated_capital": p.allocated_capital,
                "status": p.status}

    async def get_portfolios(self, limit: int = 50) -> list[dict]:
        result = await self.session.execute(
            select(Portfolio).order_by(desc(Portfolio.created_at)).limit(limit)
        )
        return [{"id": p.id, "name": p.name, "status": p.status,
                 "total_capital": p.total_capital}
                for p in result.scalars().all()]

    async def add_account(self, portfolio_id: int, account: dict) -> int:
        a = PortfolioAccount(
            portfolio_id=portfolio_id,
            account_id=account.get("account_id", ""),
            account_type=account.get("account_type", "paper"),
            name=account.get("name", ""),
            allocation_pct=account.get("allocation_pct", 0),
            allocation_method=account.get("allocation_method", "equal"),
            priority=account.get("priority", 0),
            balance=account.get("balance", 0),
        )
        self.session.add(a)
        await self.session.flush()
        return a.id

    async def get_accounts(self, portfolio_id: int) -> list[dict]:
        result = await self.session.execute(
            select(PortfolioAccount).where(
                PortfolioAccount.portfolio_id == portfolio_id)
        )
        return [
            {"id": a.id, "account_id": a.account_id, "account_type": a.account_type,
             "name": a.name, "allocation_pct": a.allocation_pct,
             "allocation_method": a.allocation_method,
             "priority": a.priority, "is_enabled": a.is_enabled,
             "balance": a.balance}
            for a in result.scalars().all()
        ]

    async def store_statistic(self, portfolio_id: int, stats: dict) -> int:
        s = PortfolioStatistic(
            portfolio_id=portfolio_id,
            total_equity=stats.get("total_equity", 0),
            daily_pnl=stats.get("daily_pnl", 0),
            unrealized_pnl=stats.get("unrealized_pnl", 0),
            realized_pnl=stats.get("realized_pnl", 0),
            drawdown_pct=stats.get("drawdown_pct", 0),
            exposure=stats.get("exposure", 0),
            capital_utilization=stats.get("capital_utilization", 0),
            account_count=stats.get("account_count", 0),
        )
        self.session.add(s)
        await self.session.flush()
        return s.id

    async def get_statistics(self, portfolio_id: int,
                             limit: int = 100) -> list[dict]:
        result = await self.session.execute(
            select(PortfolioStatistic)
            .where(PortfolioStatistic.portfolio_id == portfolio_id)
            .order_by(desc(PortfolioStatistic.timestamp)).limit(limit)
        )
        return [
            {"id": s.id, "total_equity": s.total_equity, "daily_pnl": s.daily_pnl,
             "unrealized_pnl": s.unrealized_pnl, "realized_pnl": s.realized_pnl,
             "drawdown_pct": s.drawdown_pct, "exposure": s.exposure,
             "capital_utilization": s.capital_utilization,
             "account_count": s.account_count}
            for s in result.scalars().all()
        ]
