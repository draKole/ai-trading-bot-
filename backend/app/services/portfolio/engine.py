"""Portfolio Engine — coordinates multiple accounts without duplicating pipeline logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class PortfolioConfig:
    name: str = ""
    description: str = ""
    total_capital: float = 0.0

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "total_capital": self.total_capital}


@dataclass
class AccountEntry:
    """An account within a portfolio."""
    account_id: str = ""
    account_type: str = "paper"
    name: str = ""
    allocation_pct: float = 0.0
    allocation_method: str = "equal"
    priority: int = 0
    is_enabled: bool = True
    balance: float = 0.0

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id, "account_type": self.account_type,
            "name": self.name, "allocation_pct": self.allocation_pct,
            "allocation_method": self.allocation_method,
            "priority": self.priority, "is_enabled": self.is_enabled,
            "balance": self.balance,
        }


@dataclass
class AllocationResult:
    """Result of capital allocation calculation."""
    account_id: str
    allocated_capital: float
    allocation_pct: float

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "allocated_capital": round(self.allocated_capital, 2),
            "allocation_pct": round(self.allocation_pct, 4),
        }


@dataclass
class PortfolioSnapshot:
    """Aggregated portfolio snapshot."""
    portfolio_id: str = ""
    total_equity: float = 0.0
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    drawdown_pct: float = 0.0
    exposure: float = 0.0
    capital_utilization: float = 0.0
    account_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "portfolio_id": self.portfolio_id,
            "total_equity": round(self.total_equity, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "drawdown_pct": round(self.drawdown_pct, 4),
            "exposure": round(self.exposure, 2),
            "capital_utilization": round(self.capital_utilization, 4),
            "account_count": self.account_count,
        }


def allocate_capital(accounts: list[AccountEntry],
                     total_capital: float,
                     method: str = "equal") -> list[AllocationResult]:
    """Allocate capital across accounts.

    Methods: equal, fixed_pct, fixed_dollar, risk_weighted, manual.
    """
    if not accounts or total_capital <= 0:
        return []

    enabled = [a for a in accounts if a.is_enabled]
    if not enabled:
        return []

    results: list[AllocationResult] = []

    if method == "equal":
        share = total_capital / len(enabled)
        for a in enabled:
            results.append(AllocationResult(
                account_id=a.account_id,
                allocated_capital=share,
                allocation_pct=1.0 / len(enabled),
            ))
    elif method == "fixed_pct":
        for a in enabled:
            alloc = total_capital * (a.allocation_pct / 100.0)
            results.append(AllocationResult(
                account_id=a.account_id,
                allocated_capital=alloc,
                allocation_pct=a.allocation_pct / 100.0,
            ))
    elif method == "fixed_dollar":
        for a in enabled:
            results.append(AllocationResult(
                account_id=a.account_id,
                allocated_capital=min(a.allocation_pct, total_capital),
                allocation_pct=min(a.allocation_pct, total_capital) / total_capital if total_capital > 0 else 0,
            ))
    elif method == "risk_weighted":
        total_priority = sum(a.priority for a in enabled) or 1
        for a in enabled:
            weight = a.priority / total_priority
            results.append(AllocationResult(
                account_id=a.account_id,
                allocated_capital=total_capital * weight,
                allocation_pct=weight,
            ))
    else:  # manual — use existing allocation_pct
        for a in enabled:
            alloc = total_capital * (a.allocation_pct / 100.0)
            results.append(AllocationResult(
                account_id=a.account_id,
                allocated_capital=alloc,
                allocation_pct=a.allocation_pct / 100.0,
            ))

    return results


def calculate_portfolio_risk(accounts: list[AccountEntry],
                             positions: list[dict],
                             total_capital: float) -> dict:
    """Calculate portfolio-level risk metrics."""
    total_exposure = sum(p.get("unrealized_pnl", 0) for p in positions)
    max_dd_pct = max((p.get("drawdown_pct", 0) for p in positions), default=0.0)
    utilization = abs(total_exposure) / total_capital if total_capital > 0 else 0.0

    return {
        "total_exposure": round(total_exposure, 2),
        "max_drawdown_pct": round(max_dd_pct, 4),
        "capital_utilization": round(utilization, 4),
        "account_count": len([a for a in accounts if a.is_enabled]),
        "total_capital": round(total_capital, 2),
    }


class PortfolioController:
    """Coordinates multiple accounts. Never duplicates pipeline logic."""

    def __init__(self):
        self._portfolios: dict[str, dict] = {}

    def create_portfolio(self, name: str, total_capital: float = 0.0,
                         description: str = "") -> dict:
        pid = str(uuid4())
        self._portfolios[pid] = {
            "id": pid, "name": name, "total_capital": total_capital,
            "description": description, "accounts": [], "status": "active",
        }
        return self._portfolios[pid]

    def add_account(self, portfolio_id: str, account: AccountEntry) -> dict:
        p = self._get(portfolio_id)
        p["accounts"].append(account)
        return p

    def get_portfolio(self, portfolio_id: str) -> dict | None:
        return self._portfolios.get(portfolio_id)

    def list_portfolios(self) -> list[dict]:
        return list(self._portfolios.values())

    def allocate(self, portfolio_id: str,
                 method: str = "equal") -> list[AllocationResult]:
        p = self._get(portfolio_id)
        return allocate_capital(p["accounts"], p["total_capital"], method)

    def get_statistics(self, portfolio_id: str) -> dict:
        p = self._get(portfolio_id)
        accounts = p["accounts"]
        total_equity = sum(a.balance for a in accounts if a.is_enabled)
        enabled = [a for a in accounts if a.is_enabled]
        return {
            "portfolio_id": portfolio_id,
            "name": p["name"],
            "total_capital": p["total_capital"],
            "total_equity": round(total_equity, 2),
            "account_count": len(enabled),
            "status": p["status"],
        }

    def get_performance_ranking(self, portfolio_id: str) -> list[dict]:
        p = self._get(portfolio_id)
        ranked = sorted(
            [a for a in p["accounts"] if a.is_enabled],
            key=lambda a: a.balance, reverse=True,
        )
        return [
            {"rank": i + 1, "account_id": a.account_id, "name": a.name,
             "balance": a.balance, "allocation_pct": a.allocation_pct}
            for i, a in enumerate(ranked)
        ]

    def _get(self, portfolio_id: str) -> dict:
        p = self._portfolios.get(portfolio_id)
        if p is None:
            raise ValueError(f"Portfolio not found: {portfolio_id}")
        return p
