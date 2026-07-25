"""Phase 8A Tests — Portfolio & Multi-Account Management.

Tests for portfolio creation, account management, capital allocation,
risk aggregation, statistics, and API integration.
"""

import json

import pytest

from app.services.portfolio.engine import (
    PortfolioController, AccountEntry, AllocationResult,
    allocate_capital, calculate_portfolio_risk,
)


# ─── Helpers ─────────────────────────────────────────────────

def _make_account(aid: str = "acc-1", pct: float = 25.0,
                  balance: float = 0.0) -> AccountEntry:
    return AccountEntry(account_id=aid, allocation_pct=pct,
                        balance=balance, is_enabled=True)


# ─── Allocation Tests ──────────────────────────────────────

class TestAllocation:
    """Capital allocation methods."""

    def test_equal_allocation(self):
        accounts = [_make_account("a1"), _make_account("a2"),
                    _make_account("a3"), _make_account("a4")]
        results = allocate_capital(accounts, 100_000.0, "equal")
        assert len(results) == 4
        for r in results:
            assert r.allocated_capital == 25_000.0

    def test_fixed_pct_allocation(self):
        accounts = [
            _make_account("a1", pct=50),
            _make_account("a2", pct=30),
            _make_account("a3", pct=20),
        ]
        results = allocate_capital(accounts, 100_000.0, "fixed_pct")
        assert results[0].allocated_capital == 50_000.0
        assert results[1].allocated_capital == 30_000.0
        assert results[2].allocated_capital == 20_000.0

    def test_risk_weighted_allocation(self):
        accounts = [
            AccountEntry(account_id="a1", priority=3, is_enabled=True),
            AccountEntry(account_id="a2", priority=1, is_enabled=True),
        ]
        results = allocate_capital(accounts, 100_000.0, "risk_weighted")
        assert results[0].allocated_capital == 75_000.0  # 3/4
        assert results[1].allocated_capital == 25_000.0  # 1/4

    def test_empty_accounts(self):
        results = allocate_capital([], 100_000.0)
        assert len(results) == 0

    def test_all_disabled(self):
        accounts = [
            AccountEntry(account_id="a1", is_enabled=False),
            AccountEntry(account_id="a2", is_enabled=False),
        ]
        results = allocate_capital(accounts, 100_000.0)
        assert len(results) == 0

    def test_zero_capital(self):
        accounts = [_make_account()]
        results = allocate_capital(accounts, 0.0)
        assert len(results) == 0

    def test_fixed_dollar(self):
        accounts = [_make_account("a1", pct=10_000)]
        results = allocate_capital(accounts, 100_000.0, "fixed_dollar")
        assert results[0].allocated_capital == 10_000.0


# ─── Portfolio Controller Tests ────────────────────────────

class TestPortfolioController:
    """Portfolio lifecycle and account management."""

    def test_create_portfolio(self):
        c = PortfolioController()
        p = c.create_portfolio("Main", 500_000.0)
        assert p["name"] == "Main"
        assert p["total_capital"] == 500_000.0

    def test_add_account(self):
        c = PortfolioController()
        p = c.create_portfolio("Main")
        acc = _make_account("paper-1", pct=50)
        c.add_account(p["id"], acc)
        updated = c.get_portfolio(p["id"])
        assert len(updated["accounts"]) == 1

    def test_get_nonexistent(self):
        c = PortfolioController()
        assert c.get_portfolio("nonexistent") is None

    def test_list_portfolios(self):
        c = PortfolioController()
        c.create_portfolio("P1")
        c.create_portfolio("P2")
        assert len(c.list_portfolios()) == 2

    def test_statistics(self):
        c = PortfolioController()
        p = c.create_portfolio("Main", 100_000.0)
        c.add_account(p["id"], AccountEntry(account_id="a1", balance=50_000, is_enabled=True))
        c.add_account(p["id"], AccountEntry(account_id="a2", balance=30_000, is_enabled=True))
        stats = c.get_statistics(p["id"])
        assert stats["total_equity"] == 80_000.0
        assert stats["account_count"] == 2

    def test_performance_ranking(self):
        c = PortfolioController()
        p = c.create_portfolio("Main")
        c.add_account(p["id"], AccountEntry(account_id="a1", balance=100_000, is_enabled=True, name="Top"))
        c.add_account(p["id"], AccountEntry(account_id="a2", balance=50_000, is_enabled=True, name="Bottom"))
        ranking = c.get_performance_ranking(p["id"])
        assert ranking[0]["account_id"] == "a1"
        assert ranking[1]["account_id"] == "a2"

    def test_allocate_through_controller(self):
        c = PortfolioController()
        p = c.create_portfolio("Main", 200_000.0)
        c.add_account(p["id"], _make_account("a1"))
        c.add_account(p["id"], _make_account("a2"))
        c.add_account(p["id"], _make_account("a3"))
        c.add_account(p["id"], _make_account("a4"))
        results = c.allocate(p["id"], "equal")
        assert len(results) == 4

    def test_large_portfolio(self):
        """100+ accounts."""
        c = PortfolioController()
        p = c.create_portfolio("Large", 1_000_000.0)
        for i in range(100):
            c.add_account(p["id"], AccountEntry(account_id=f"acc-{i}",
                                                 allocation_pct=1.0,
                                                 is_enabled=True))
        stats = c.get_statistics(p["id"])
        assert stats["account_count"] == 100


# ─── Risk Calculation Tests ────────────────────────────────

class TestPortfolioRisk:
    """Portfolio-level risk aggregation."""

    def test_calculate_risk(self):
        accounts = [_make_account("a1", balance=50_000),
                    _make_account("a2", balance=50_000)]
        positions = [
            {"unrealized_pnl": 5000.0, "drawdown_pct": 2.0},
            {"unrealized_pnl": -2000.0, "drawdown_pct": 1.0},
        ]
        risk = calculate_portfolio_risk(accounts, positions, 100_000.0)
        assert risk["total_exposure"] == 3000.0
        assert risk["max_drawdown_pct"] == 2.0
        assert risk["account_count"] == 2


# ─── Serialization Tests ────────────────────────────────────

class TestSerialization:
    """Dataclass serialization."""

    def test_account_entry_to_dict(self):
        a = AccountEntry(account_id="test", name="Test", balance=50_000)
        d = a.to_dict()
        assert d["account_id"] == "test"
        assert d["balance"] == 50_000

    def test_allocation_result_to_dict(self):
        r = AllocationResult(account_id="a1", allocated_capital=25000, allocation_pct=0.25)
        d = r.to_dict()
        assert d["allocated_capital"] == 25000


# ─── API Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portfolio_list_api():
    """Test /api/v1/portfolio/portfolios."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/portfolio/portfolios")
            assert response.status_code == 200
            data = response.json()
            assert "count" in data
    except ConnectionRefusedError:
        pytest.skip("Database not available")
