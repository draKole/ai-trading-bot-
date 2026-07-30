"""Phase 5C Tests — Performance Analytics.

Tests for all analytics functions: risk-adjusted returns, drawdown
analytics, return analytics, trade analytics, rolling analytics,
reports, comparisons, and API integration.
"""

import json
import math
import pytest

from app.services.analytics.engine import (
    compute_sharpe_ratio, compute_sortino_ratio, compute_calmar_ratio,
    compute_drawdown_analytics, compute_returns_analytics,
    compute_trade_analytics, compute_rolling_analytics,
    generate_report, compare_strategies, AnalyticsController,
)

from datetime import datetime

from app.models.backtesting import BacktestRun
from app.core.database import async_session_factory
# ─── Helpers ─────────────────────────────────────────────────

def _make_trade(pnl: float = 100.0, r_multiple: float = 1.0,
                duration: int = 300, direction: str = "bullish",
                entry: str = "2025-06-16T09:30:00",
                exit_t: str = "2025-06-16T09:35:00") -> dict:
    return {
        "pnl": pnl, "r_multiple": r_multiple,
        "duration_seconds": duration, "direction": direction,
        "entry_time": entry, "exit_time": exit_t,
    }


def _make_trades(n: int = 10) -> list[dict]:
    trades = []
    for i in range(n):
        pnl = 100.0 if i % 2 == 0 else -50.0
        minute = 30 + i * 5
        trades.append(_make_trade(
            pnl=pnl, r_multiple=pnl / 100.0, duration=300,
            entry=f"2025-06-16T09:{minute:02d}:00",
            exit_t=f"2025-06-16T09:{minute+4:02d}:00",
        ))
    return trades


def _make_equity(trades: list[dict], initial: float = 100_000.0) -> list[dict]:
    points = []
    balance = initial
    peak = initial
    for i, t in enumerate(trades):
        balance += t["pnl"]
        peak = max(peak, balance)
        dd = peak - balance
        points.append({
            "trade_index": i,
            "equity": round(balance, 2),
            "drawdown": round(dd, 2),
            "drawdown_pct": round(dd / peak * 100, 4) if peak > 0 else 0.0,
            "peak_equity": round(peak, 2),
        })
    return points


# ─── Risk-Adjusted Returns ──────────────────────────────────

class TestRiskAdjusted:
    """Sharpe, Sortino, Calmar ratios."""

    def test_sharpe_positive_returns(self):
        returns = [0.001 + (i * 0.0001) for i in range(100)]  # variable positive returns
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe > 0

    def test_sharpe_zero_variance(self):
        returns = [0.001, 0.001]
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe == 0.0

    def test_sharpe_empty(self):
        assert compute_sharpe_ratio([]) == 0.0

    def test_sharpe_single(self):
        assert compute_sharpe_ratio([0.01]) == 0.0

    def test_sortino_positive(self):
        returns = [0.002, -0.001, 0.003, 0.001, -0.0005, 0.002] * 20  # mixed, mostly positive
        sortino = compute_sortino_ratio(returns)
        assert sortino > 0

    def test_sortino_empty(self):
        assert compute_sortino_ratio([]) == 0.0

    def test_calmar_ratio(self):
        assert compute_calmar_ratio(0.15, -10.0) > 0

    def test_calmar_zero_dd(self):
        assert compute_calmar_ratio(0.15, 0.0) == 0.0

    def test_sharpe_deterministic(self):
        returns = [0.001, -0.002, 0.003, 0.001, -0.001] * 10
        s1 = compute_sharpe_ratio(list(returns))
        s2 = compute_sharpe_ratio(list(returns))
        assert s1 == s2


# ─── Drawdown Analytics ────────────────────────────────────

class TestDrawdownAnalytics:
    """Drawdown statistics."""

    def test_empty(self):
        result = compute_drawdown_analytics([])
        assert result["average_drawdown"] == 0.0
        assert result["max_dd_duration"] == 0

    def test_with_drawdowns(self):
        trades = [_make_trade(100), _make_trade(-200), _make_trade(50)]
        equity = _make_equity(trades)
        result = compute_drawdown_analytics(equity)
        assert result["ulcer_index"] > 0
        assert result["average_drawdown"] > 0

    def test_no_drawdowns(self):
        trades = [_make_trade(100), _make_trade(200), _make_trade(300)]
        equity = _make_equity(trades)
        result = compute_drawdown_analytics(equity)
        assert result["average_drawdown"] == 0.0
        assert result["ulcer_index"] == 0.0

    def test_recovery_factor(self):
        trades = [_make_trade(100), _make_trade(-50), _make_trade(200)]
        equity = _make_equity(trades)
        result = compute_drawdown_analytics(equity)
        assert result["recovery_factor"] >= 0


# ─── Returns Analytics ─────────────────────────────────────

class TestReturnsAnalytics:
    """CAGR, monthly returns."""

    def test_empty(self):
        result = compute_returns_analytics([])
        assert result["cagr"] == 0.0
        assert result["monthly_returns"] == {}

    def test_with_trades(self):
        trades = _make_trades(20)
        result = compute_returns_analytics(trades)
        assert "monthly_returns" in result
        assert "cagr" in result

    def test_monthly_buckets(self):
        trades = [
            _make_trade(100, entry="2025-01-15T10:00:00"),
            _make_trade(200, entry="2025-01-20T10:00:00"),
            _make_trade(-50, entry="2025-02-10T10:00:00"),
        ]
        result = compute_returns_analytics(trades)
        monthly = result["monthly_returns"]
        assert len(monthly) >= 2
        assert result["best_month_label"] != ""

    def test_cagr_with_equity(self):
        trades = [_make_trade(100), _make_trade(200)]
        equity = [
            {"trade_index": 0, "equity": 100_000.0, "timestamp": "2025-01-01T00:00:00Z"},
            {"trade_index": 1, "equity": 100_300.0, "timestamp": "2026-01-01T00:00:00Z"},
        ]
        result = compute_returns_analytics(trades, equity)
        assert result["cagr"] > 0


# ─── Trade Analytics ───────────────────────────────────────

class TestTradeAnalytics:
    """Advanced trade statistics."""

    def test_empty(self):
        result = compute_trade_analytics([])
        assert result["avg_hold_time_seconds"] == 0.0

    def test_with_trades(self):
        trades = _make_trades(10)
        result = compute_trade_analytics(trades)
        assert result["avg_hold_time_seconds"] > 0
        assert result["median_hold_time_seconds"] > 0
        assert "pnl_distribution" in result
        assert "r_distribution" in result
        assert result["win_loss_histogram"]["wins"] > 0

    def test_win_loss_histogram(self):
        trades = [
            _make_trade(100), _make_trade(-50),
            _make_trade(200), _make_trade(0),
        ]
        result = compute_trade_analytics(trades)
        assert result["win_loss_histogram"]["wins"] == 2
        assert result["win_loss_histogram"]["losses"] == 1
        assert result["win_loss_histogram"]["breakeven"] == 1

    def test_consecutive_distribution(self):
        trades = [
            _make_trade(100), _make_trade(200), _make_trade(-50),
            _make_trade(-30), _make_trade(300),
        ]
        result = compute_trade_analytics(trades)
        assert "consecutive_distribution" in result


# ─── Rolling Analytics ─────────────────────────────────────

class TestRollingAnalytics:
    """Rolling statistics."""

    def test_empty(self):
        result = compute_rolling_analytics([])
        assert result["rolling_equity"] == []

    def test_fewer_than_window(self):
        trades = _make_trades(5)
        result = compute_rolling_analytics(trades, window=10)
        assert result["rolling_equity"] == []

    def test_with_trades(self):
        trades = _make_trades(15)
        result = compute_rolling_analytics(trades, window=5)
        assert len(result["rolling_equity"]) == 15
        assert len(result["rolling_win_rate"]) == 11  # 15 - 5 + 1 = 11

    def test_rolling_deterministic(self):
        trades = _make_trades(15)
        r1 = compute_rolling_analytics(list(trades))
        r2 = compute_rolling_analytics(list(trades))
        assert r1 == r2


# ─── Report Generation ─────────────────────────────────────

class TestReport:
    """Full report generation."""

    def test_generate_report(self):
        trades = _make_trades(20)
        equity = _make_equity(trades)
        metrics = {"total_trades": 20, "net_profit": 500.0, "win_rate": 0.55,
                   "profit_factor": 1.5, "expectancy": 25.0, "max_drawdown_pct": 5.0}

        report = generate_report(
            {"id": 1, "instrument": "ES", "timeframe": "5m"},
            trades, metrics, equity,
        )
        assert report["report_type"] == "full"
        assert "executive_summary" in report
        assert "risk_summary" in report
        assert "performance_summary" in report
        assert "trade_statistics" in report
        assert "charts" in report
        assert report["charts"]["equity_curve"]

    def test_empty_report(self):
        report = generate_report({"id": 1}, [], {}, [])
        assert report["report_type"] == "full"
        assert report["executive_summary"]["total_trades"] == 0

    def test_report_deterministic(self):
        trades = _make_trades(10)
        equity = _make_equity(trades)
        metrics = {"total_trades": 10, "net_profit": 500.0, "win_rate": 0.6,
                   "profit_factor": 1.5, "expectancy": 30.0, "max_drawdown_pct": 3.0}
        r1 = generate_report({"id": 1}, list(trades), dict(metrics), list(equity))
        r2 = generate_report({"id": 1}, list(trades), dict(metrics), list(equity))
        # Compare key sections (JSON serializable)
        assert r1["executive_summary"] == r2["executive_summary"]
        assert r1["risk_summary"] == r2["risk_summary"]


# ─── Strategy Comparison ───────────────────────────────────

class TestComparison:
    """Strategy comparison."""

    def test_empty(self):
        result = compare_strategies([])
        assert result["runs"] == []

    def test_single_run(self):
        runs = [{"run_id": 1, "metrics": {
            "net_profit": 500.0, "win_rate": 0.6,
            "profit_factor": 1.5, "expectancy": 30.0,
            "max_drawdown_pct": 5.0, "total_trades": 10,
            "sharpe_ratio": 1.5,
        }}]
        result = compare_strategies(runs)
        assert result["comparison"]["run_count"] == 1
        assert result["comparison"]["best_run"] is not None

    def test_multiple_runs(self):
        runs = [
            {"run_id": 1, "metrics": {"net_profit": 500.0, "win_rate": 0.6,
             "profit_factor": 1.5, "expectancy": 30.0, "max_drawdown_pct": 5.0,
             "total_trades": 10, "sharpe_ratio": 1.5}},
            {"run_id": 2, "metrics": {"net_profit": 800.0, "win_rate": 0.55,
             "profit_factor": 1.8, "expectancy": 40.0, "max_drawdown_pct": 3.0,
             "total_trades": 12, "sharpe_ratio": 1.8}},
        ]
        result = compare_strategies(runs)
        assert result["comparison"]["run_count"] == 2
        assert result["comparison"]["best_run"]["run_id"] == 2


# ─── Controller Tests ──────────────────────────────────────

class TestController:
    """AnalyticsController integration."""

    def test_analyze(self):
        controller = AnalyticsController()
        trades = _make_trades(10)
        equity = _make_equity(trades)
        metrics = {"total_trades": 10, "net_profit": 500.0, "win_rate": 0.6,
                   "profit_factor": 1.5, "expectancy": 30.0, "max_drawdown_pct": 3.0}
        report = controller.analyze({"id": 1}, trades, metrics, equity)
        assert report["report_type"] == "full"

    def test_summarize(self):
        controller = AnalyticsController()
        metrics = {"total_trades": 10, "net_profit": 500.0, "win_rate": 0.6,
                   "profit_factor": 1.5, "expectancy": 30.0, "max_drawdown_pct": 3.0}
        summary = controller.summarize({"instrument": "ES", "trades": []}, metrics)
        assert summary["instrument"] == "ES"
        assert "sharpe_ratio" in summary

    def test_compare(self):
        controller = AnalyticsController()
        runs = [{"run_id": 1, "metrics": {"net_profit": 500.0, "win_rate": 0.6,
                 "profit_factor": 1.5, "expectancy": 30.0, "max_drawdown_pct": 5.0,
                 "total_trades": 10, "sharpe_ratio": 1.5}}]
        result = controller.compare(runs)
        assert result["comparison"]["run_count"] == 1


# ─── Large Dataset Tests ────────────────────────────────────

class TestLargeDataset:
    """Performance with large trade sets."""

    def test_large_trade_set(self):
        trades = []
        for i in range(500):
            pnl = (100.0 if i % 3 != 0 else -50.0)
            trades.append(_make_trade(pnl=pnl, entry=f"2025-{(i//20)+1:02d}-{(i%28)+1:02d}T10:00:00"))
        equity = _make_equity(trades)
        result = compute_returns_analytics(trades, equity)
        assert len(result["monthly_returns"]) > 1
        trade_result = compute_trade_analytics(trades)
        assert trade_result["avg_hold_time_seconds"] > 0
        rolling = compute_rolling_analytics(trades, window=20)
        assert len(rolling["rolling_win_rate"]) > 0


# ─── Serialization Tests ────────────────────────────────────

class TestSerialization:
    """Report JSON serialization."""

    def test_report_json_serializable(self):
        trades = _make_trades(10)
        equity = _make_equity(trades)
        metrics = {"total_trades": 10, "net_profit": 500.0, "win_rate": 0.6,
                   "profit_factor": 1.5, "expectancy": 30.0, "max_drawdown_pct": 3.0}
        report = generate_report({"id": 1}, trades, metrics, equity)
        s = json.dumps(report)
        assert isinstance(s, str)
        assert len(s) > 100

    def test_comparison_json_serializable(self):
        runs = [{"run_id": 1, "metrics": {"net_profit": 500.0, "win_rate": 0.6,
                 "profit_factor": 1.5, "expectancy": 30.0, "max_drawdown_pct": 5.0,
                 "total_trades": 10, "sharpe_ratio": 1.5}}]
        result = compare_strategies(runs)
        s = json.dumps(result)
        assert isinstance(s, str)


# ─── API Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_generate_api():
    """Test /api/v1/analytics/generate endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    trades = _make_trades(10)
    equity = _make_equity(trades)
    metrics = {"total_trades": 10, "net_profit": 500.0, "win_rate": 0.6,
               "profit_factor": 1.5, "expectancy": 30.0, "max_drawdown_pct": 3.0}
 
    async with async_session_factory() as session:
        existing = await session.get(BacktestRun, 1)

        if existing is None:
            session.add(
                BacktestRun(
                    id=1,
                    instrument="ES",
                    timeframe="5m",
                    start_time=datetime.utcnow(),
                    end_time=datetime.utcnow(),
                    status="completed",
                    total_bars=0,
                )
            )
            await session.commit()

        result = await session.get(BacktestRun, 1)
        print("BACKTEST:", result)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/analytics/generate",
                params={
                    "run_id": 1,
                    "trades_json": json.dumps(trades),
                    "metrics_json": json.dumps(metrics),
                    "equity_json": json.dumps(equity),
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "report_id" in data
            assert "summary" in data
    except ConnectionRefusedError:
        pytest.skip("Database not available")


@pytest.mark.asyncio
async def test_analytics_compare_api():
    """Test /api/v1/analytics/compare endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    runs = [
        {"run_id": 1, "metrics": {"net_profit": 500.0, "win_rate": 0.6,
         "profit_factor": 1.5, "expectancy": 30.0, "max_drawdown_pct": 5.0,
         "total_trades": 10, "sharpe_ratio": 1.5}},
        {"run_id": 2, "metrics": {"net_profit": 800.0, "win_rate": 0.55,
         "profit_factor": 1.8, "expectancy": 40.0, "max_drawdown_pct": 3.0,
         "total_trades": 12, "sharpe_ratio": 1.8}},
    ]

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/analytics/compare",
                params={"runs_json": json.dumps(runs)},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["comparison"]["run_count"] == 2
    except ConnectionRefusedError:
        pytest.skip("Database not available")
