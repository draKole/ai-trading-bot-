"""Phase 8B Tests — Strategy Optimization & Walk-Forward Analysis.

Tests for grid search, random search, walk-forward, Monte Carlo,
strategy comparison, and API integration.
"""

import json
import math

import pytest

from app.services.optimization.engine import (
    OptimizationController, ParamRange,
    grid_search, random_search, walk_forward_splits,
    monte_carlo_simulation, compare_strategies,
)


# ─── Grid Search ──────────────────────────────────────────

class TestGridSearch:
    """Grid search generation."""

    def test_single_param(self):
        ranges = [ParamRange("min_rr", 2.0, 4.0, 1.0)]
        combos = grid_search(ranges)
        assert len(combos) == 3  # 2.0, 3.0, 4.0

    def test_two_params(self):
        ranges = [
            ParamRange("min_rr", 2.0, 3.0, 1.0),
            ParamRange("risk_pct", 1.0, 2.0, 1.0),
        ]
        combos = grid_search(ranges)
        assert len(combos) == 4  # 2x2

    def test_three_params(self):
        ranges = [
            ParamRange("a", 1.0, 2.0, 1.0),
            ParamRange("b", 10.0, 20.0, 10.0),
            ParamRange("c", 0.1, 0.2, 0.1),
        ]
        combos = grid_search(ranges)
        assert len(combos) == 8  # 2x2x2

    def test_empty(self):
        combos = grid_search([])
        assert combos == [{}]

    def test_large_grid(self):
        """10,000+ combinations."""
        ranges = [
            ParamRange("a", 1.0, 10.0, 1.0),
            ParamRange("b", 1.0, 10.0, 1.0),
            ParamRange("c", 1.0, 10.0, 1.0),
            ParamRange("d", 1.0, 10.0, 1.0),
        ]
        combos = grid_search(ranges)
        assert len(combos) == 10_000  # 10x10x10x10

    def test_deterministic(self):
        ranges = [ParamRange("x", 1.0, 5.0, 2.0)]
        c1 = grid_search(ranges)
        c2 = grid_search(ranges)
        assert c1 == c2


# ─── Random Search ────────────────────────────────────────

class TestRandomSearch:
    """Random search generation."""

    def test_count(self):
        ranges = [ParamRange("a", 0.0, 1.0, 0.1)]
        combos = random_search(ranges, n_iterations=50, seed=42)
        assert len(combos) == 50

    def test_deterministic_with_seed(self):
        ranges = [ParamRange("a", 0.0, 10.0, 0.1)]
        c1 = random_search(ranges, n_iterations=20, seed=42)
        c2 = random_search(ranges, n_iterations=20, seed=42)
        assert c1 == c2

    def test_different_seeds(self):
        ranges = [ParamRange("a", 0.0, 10.0, 0.1)]
        c1 = random_search(ranges, n_iterations=20, seed=1)
        c2 = random_search(ranges, n_iterations=20, seed=2)
        assert c1 != c2


# ─── Walk-Forward ─────────────────────────────────────────

class TestWalkForward:
    """Walk-forward split generation."""

    def test_basic_split(self):
        splits = walk_forward_splits(100, 40, 20)
        assert len(splits) >= 2

    def test_exact_fit(self):
        splits = walk_forward_splits(60, 20, 20)
        assert len(splits) == 2  # 0-40, 20-60 (2 windows)

    def test_not_enough_data(self):
        splits = walk_forward_splits(10, 20, 10)
        assert len(splits) == 0


# ─── Monte Carlo ──────────────────────────────────────────

class TestMonteCarlo:
    """Monte Carlo simulation."""

    def test_basic_simulation(self):
        trades = [{"pnl": 100}, {"pnl": -50}, {"pnl": 200},
                  {"pnl": -30}, {"pnl": 150}] * 20
        result = monte_carlo_simulation(trades, iterations=500, seed=42)
        assert result["mean_equity"] > 0
        assert result["iterations"] == 500

    def test_empty_trades(self):
        result = monte_carlo_simulation([], iterations=100)
        assert result["iterations"] == 0
        assert result["mean_equity"] == 0.0

    def test_deterministic(self):
        trades = [{"pnl": 100}, {"pnl": -50}] * 50
        r1 = monte_carlo_simulation(trades, iterations=100, seed=42)
        r2 = monte_carlo_simulation(list(trades), iterations=100, seed=42)
        assert r1["mean_equity"] == r2["mean_equity"]
        assert r1["risk_of_ruin"] == r2["risk_of_ruin"]


# ─── Strategy Comparison ──────────────────────────────────

class TestStrategyComparison:
    """Strategy comparison and ranking."""

    def test_ranking(self):
        results = [
            {"params": {"min_rr": 2.0}, "net_profit": 500.0, "win_rate": 0.6,
             "profit_factor": 1.5, "expectancy": 30.0},
            {"params": {"min_rr": 3.0}, "net_profit": 800.0, "win_rate": 0.55,
             "profit_factor": 1.8, "expectancy": 40.0},
            {"params": {"min_rr": 1.5}, "net_profit": 200.0, "win_rate": 0.5,
             "profit_factor": 1.2, "expectancy": 10.0},
        ]
        comparison = compare_strategies(results)
        assert comparison["total_compared"] == 3
        assert comparison["best"]["params"]["min_rr"] == 3.0  # Best = highest profit

    def test_empty(self):
        result = compare_strategies([])
        assert result["rankings"] == []
        assert result["best"] is None


# ─── Controller Tests ─────────────────────────────────────

class TestController:
    """OptimizationController integration."""

    def test_create_run(self):
        c = OptimizationController()
        run = c.create_run("Test", "grid")
        assert run["name"] == "Test"
        assert run["status"] == "pending"

    def test_grid_search_run(self):
        c = OptimizationController()
        ranges = [ParamRange("min_rr", 2.0, 4.0, 1.0)]
        run = c.run_grid_search(ranges)
        assert run["status"] == "completed"
        assert run["total_combinations"] == 3
        assert run["best_params"] is not None

    def test_monte_carlo_run(self):
        c = OptimizationController()
        trades = [{"pnl": 100}, {"pnl": -50}] * 50
        result = c.run_monte_carlo(trades, iterations=200, seed=123)
        assert result["mean_equity"] > 0

    def test_list_runs(self):
        c = OptimizationController()
        c.create_run("R1")
        c.create_run("R2")
        assert len(c.list_runs()) == 2


# ─── Serialization ────────────────────────────────────────

class TestSerialization:
    """Parameter range serialization."""

    def test_param_range(self):
        p = ParamRange("test", 0.0, 10.0, 2.0)
        assert p.generate_values() == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]


# ─── API Tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_optimization_runs_api():
    """Test /api/v1/optimization/runs endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/optimization/runs")
            assert response.status_code == 200
    except ConnectionRefusedError:
        pytest.skip("Database not available")
