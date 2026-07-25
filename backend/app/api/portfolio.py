"""Portfolio API — multi-account management, capital allocation, statistics."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.portfolio import (
    PortfolioService, PortfolioController,
    AccountEntry, allocate_capital,
)

router = APIRouter()

_controller = PortfolioController()


@router.get("/portfolios")
async def list_portfolios(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    portfolios = await service.get_portfolios(limit=limit)
    return {"count": len(portfolios), "portfolios": portfolios}


@router.get("/portfolios/{portfolio_id}")
async def get_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    p = await service.get_portfolio(portfolio_id)
    if p is None:
        raise HTTPException(404, f"Portfolio not found: {portfolio_id}")
    return p


@router.post("/portfolios/create")
async def create_portfolio(
    name: str = Query(...),
    description: str = Query(""),
    total_capital: float = Query(0.0),
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    p = await service.create_portfolio(name, description, total_capital)
    return {"id": p["id"], "name": p["name"]}


@router.post("/portfolios/{portfolio_id}/accounts/add")
async def add_account(
    portfolio_id: int,
    account_id: str = Query(...),
    account_type: str = Query("paper"),
    name: str = Query(""),
    allocation_pct: float = Query(0.0),
    allocation_method: str = Query("equal"),
    priority: int = Query(0),
    balance: float = Query(0.0),
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    await service.add_account(portfolio_id, {
        "account_id": account_id, "account_type": account_type,
        "name": name, "allocation_pct": allocation_pct,
        "allocation_method": allocation_method,
        "priority": priority, "balance": balance,
    })
    return {"portfolio_id": portfolio_id, "account_id": account_id, "status": "added"}


@router.get("/portfolios/{portfolio_id}/accounts")
async def list_accounts(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    accounts = await service.get_accounts(portfolio_id)
    return {"count": len(accounts), "accounts": accounts}


@router.post("/portfolios/{portfolio_id}/allocate")
async def allocate(
    portfolio_id: int,
    method: str = Query("equal"),
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    portfolio = await service.get_portfolio(portfolio_id)
    if portfolio is None:
        raise HTTPException(404, f"Portfolio not found: {portfolio_id}")
    accounts_raw = await service.get_accounts(portfolio_id)
    accounts = [AccountEntry(
        account_id=a["account_id"], account_type=a["account_type"],
        name=a["name"], allocation_pct=a["allocation_pct"],
        allocation_method=a["allocation_method"],
        priority=a["priority"], is_enabled=a["is_enabled"],
        balance=a["balance"],
    ) for a in accounts_raw]

    results = allocate_capital(accounts, portfolio["total_capital"], method)
    return {"portfolio_id": portfolio_id, "method": method,
            "allocations": [r.to_dict() for r in results]}


@router.get("/portfolios/{portfolio_id}/statistics")
async def get_statistics(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    stats = await service.get_statistics(portfolio_id, limit=50)
    return {"portfolio_id": portfolio_id, "count": len(stats), "statistics": stats}


@router.get("/portfolios/{portfolio_id}/performance")
async def get_performance(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    stats = await service.get_statistics(portfolio_id, limit=1)
    accounts = await service.get_accounts(portfolio_id)
    total_equity = sum(a["balance"] for a in accounts if a["is_enabled"])

    return {
        "portfolio_id": portfolio_id,
        "total_equity": round(total_equity, 2),
        "account_count": len(accounts),
        "latest_stats": stats[0] if stats else None,
        "accounts": accounts,
    }


@router.get("/portfolios/{portfolio_id}/risk")
async def get_risk_summary(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = PortfolioService(db)
    portfolio = await service.get_portfolio(portfolio_id)
    if portfolio is None:
        raise HTTPException(404, f"Portfolio not found: {portfolio_id}")
    accounts = await service.get_accounts(portfolio_id)
    enabled = [a for a in accounts if a["is_enabled"]]
    total_balance = sum(a["balance"] for a in enabled)
    return {
        "portfolio_id": portfolio_id,
        "total_capital": portfolio["total_capital"],
        "total_balance": round(total_balance, 2),
        "account_count": len(enabled),
        "exposure": round(abs(total_balance - portfolio["total_capital"]), 2),
    }
