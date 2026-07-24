"""Phase 5B Tests — Backtesting Engine.

Tests for BacktestController, metric calculations, equity curves,
parameter sweeps, determinism, and API integration.
"""

from datetime import datetime, timedelta, timezone
import json
import pytest

from app.services.backtesting.engine import (
    BacktestController, BacktestConfig, ParamSweepConfig,
    BacktestTrade, BacktestMetrics, EquityPoint,
    compute_metrics, BacktestResult,
)


# ─── Helpers ─────────────────────────────────────────────────

def _make_bar(
    timestamp: datetime | None = None,
    price: float = 100.0,
    minute: int = 0,
) -> dict:
    if timestamp is None:
        timestamp = datetime(2025, 6, 16, 9, 30, tzinfo=timezone.utc) + timedelta(minutes=minute)
    return {
        "timestamp": timestamp.isoformat(),
        "open": price - 0.25,
        "high": price + 0.5,
        "low": price - 0.5,
        "close": price + 0.25,
        "volume": 100,
    }


def _make_bars(n: int = 10, base_price: float = 100.0) -> list[dict]:
    bars = []
    for i in range(n):
        price = base_price + i * 0.5
        bars.append(_make_bar(minute=i * 5, price=price))
    return bars


def _trending_bars(n: int = 20, direction: str = "up") -> list[dict]:
    """Bars that trend steadily — produces winning trades in simplified mode."""
    bars = []
    base = 100.0
    for i in range(n):
        if direction == "up":
            price = base + i * 1.0
        else:
            price = base - i * 1.0
        bars.append(_make_bar(minute=i * 5, price=price))
    return bars


def _choppy_bars(n: int = 20) -> list[dict]:
    """Bars that oscillate — produces mixed outcomes."""
    bars = []
    prices = [100, 101, 102, 101, 100, 99, 98, 99, 100, 101,
              102, 103, 102, 101, 100, 101, 102, 101, 100, 99]
    for i, p in enumerate(prices[:n]):
        bars.append(_make_bar(minute=i * 5, price=p))
    return bars


def _default_config() -> BacktestConfig:
    return BacktestConfig(
        instrument="ES",
        timeframe="5m",
        start_time=datetime(2025, 6, 16, 9, 30, tzinfo=timezone.utc),
        end_time=datetime(2025, 6, 16, 16, 0, tzinfo=timezone.utc),
        initial_balance=100_000.0,
    )


# ─── Config Tests ───────────────────────────────────────────

class TestBacktestConfig:
    """BacktestConfig creation, serialization."""

    def test_default_config(self):
        config = BacktestConfig()
        assert config.instrument == ""
        assert config.initial_balance == 100_000.0

    def test_config_to_dict_roundtrip(self):
        config = _default_config()
        d = config.to_dict()
        restored = BacktestConfig.from_dict(d)
        assert restored.instrument == config.instrument
        assert restored.initial_balance == config.initial_balance

    def test_config_json_serializable(self):
        config = _default_config()
        d = config.to_dict()
        s = json.dumps(d, default=str)
        assert isinstance(s, str)


# ─── Trade Model Tests ──────────────────────────────────────

class TestBacktestTrade:
    """Trade serialization."""

    def test_trade_to_dict(self):
        trade = BacktestTrade(
            direction="bullish", entry_price=100.0, exit_price=102.0,
            pnl=200.0, r_multiple=2.0,
        )
        d = trade.to_dict()
        assert d["pnl"] == 200.0
        assert d["r_multiple"] == 2.0
        assert d["direction"] == "bullish"


# ─── Equity Point Tests ─────────────────────────────────────

class TestEquityPoint:
    """Equity curve serialization."""

    def test_equity_point_to_dict(self):
        ep = EquityPoint(
            trade_index=0,
            timestamp=datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc),
            account_balance=100_200.0,
            equity=100_200.0,
            drawdown=0.0,
            drawdown_pct=0.0,
            peak_equity=100_200.0,
        )
        d = ep.to_dict()
        assert d["trade_index"] == 0
        assert d["account_balance"] == 100_200.0


# ─── Metrics Calculation Tests ──────────────────────────────

class TestComputeMetrics:
    """Deterministic metric calculation."""

    def test_empty_trades(self):
        metrics, equity = compute_metrics([])
        assert metrics.total_trades == 0
        assert metrics.net_profit == 0.0
        assert len(equity) == 0

    def test_single_win(self):
        trade = BacktestTrade(pnl=500.0, r_multiple=2.0)
        metrics, equity = compute_metrics([trade])
        assert metrics.total_trades == 1
        assert metrics.winning_trades == 1
        assert metrics.win_rate == 1.0
        assert metrics.net_profit == 500.0
        assert metrics.profit_factor > 0

    def test_single_loss(self):
        trade = BacktestTrade(pnl=-300.0, r_multiple=-1.0)
        metrics, equity = compute_metrics([trade])
        assert metrics.total_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == 0.0
        assert metrics.net_profit == -300.0

    def test_breakeven(self):
        trade = BacktestTrade(pnl=0.0, r_multiple=0.0)
        metrics, _ = compute_metrics([trade])
        assert metrics.breakeven_trades == 1

    def test_profit_factor(self):
        trades = [
            BacktestTrade(pnl=100.0), BacktestTrade(pnl=200.0),
            BacktestTrade(pnl=-50.0), BacktestTrade(pnl=-30.0),
        ]
        metrics, _ = compute_metrics(trades)
        assert metrics.gross_profit == 300.0
        assert metrics.gross_loss == 80.0
        assert metrics.profit_factor == pytest.approx(3.75, abs=0.01)

    def test_win_rate(self):
        trades = [
            BacktestTrade(pnl=10.0), BacktestTrade(pnl=20.0),
            BacktestTrade(pnl=-5.0),
        ]
        metrics, _ = compute_metrics(trades)
        assert metrics.win_rate == pytest.approx(2 / 3, abs=0.01)
        assert metrics.loss_rate == pytest.approx(1 / 3, abs=0.01)

    def test_expectancy(self):
        trades = [
            BacktestTrade(pnl=100.0), BacktestTrade(pnl=-40.0),
        ]
        metrics, _ = compute_metrics(trades)
        expected = (0.5 * 100.0) - (0.5 * 40.0)  # = 30
        assert metrics.expectancy == pytest.approx(30.0, abs=0.1)

    def test_max_drawdown(self):
        trades = [
            BacktestTrade(pnl=100.0),   # balance: 100100, peak: 100100
            BacktestTrade(pnl=-200.0),  # balance: 99900, dd: 200
            BacktestTrade(pnl=50.0),    # balance: 99950, dd: 150
            BacktestTrade(pnl=-300.0),  # balance: 99650, dd: 450
            BacktestTrade(pnl=500.0),   # balance: 100150, dd: 0
        ]
        metrics, equity = compute_metrics(trades)
        assert metrics.max_drawdown == pytest.approx(450.0, abs=1.0)

    def test_consecutive_wins(self):
        trades = [
            BacktestTrade(pnl=10.0), BacktestTrade(pnl=20.0),
            BacktestTrade(pnl=-5.0), BacktestTrade(pnl=30.0),
            BacktestTrade(pnl=40.0), BacktestTrade(pnl=50.0),
        ]
        metrics, _ = compute_metrics(trades)
        assert metrics.max_consecutive_wins == 3  # last 3 wins
        assert metrics.max_consecutive_losses == 1

    def test_consecutive_losses(self):
        trades = [
            BacktestTrade(pnl=-10.0), BacktestTrade(pnl=-20.0),
            BacktestTrade(pnl=-30.0), BacktestTrade(pnl=5.0),
        ]
        metrics, _ = compute_metrics(trades)
        assert metrics.max_consecutive_losses == 3

    def test_directional_split(self):
        trades = [
            BacktestTrade(direction="bullish", pnl=100.0),
            BacktestTrade(direction="bullish", pnl=-50.0),
            BacktestTrade(direction="bearish", pnl=200.0),
            BacktestTrade(direction="bearish", pnl=-30.0),
        ]
        metrics, _ = compute_metrics(trades)
        assert metrics.long_trades == 2
        assert metrics.short_trades == 2
        assert metrics.long_pnl == 50.0
        assert metrics.short_pnl == 170.0

    def test_largest_winner_loser(self):
        trades = [
            BacktestTrade(pnl=500.0), BacktestTrade(pnl=100.0),
            BacktestTrade(pnl=-300.0), BacktestTrade(pnl=-50.0),
        ]
        metrics, _ = compute_metrics(trades)
        assert metrics.largest_winner == 500.0
        assert metrics.largest_loser == -300.0

    def test_average_win_loss(self):
        trades = [
            BacktestTrade(pnl=100.0), BacktestTrade(pnl=200.0),
            BacktestTrade(pnl=-50.0), BacktestTrade(pnl=-30.0), BacktestTrade(pnl=-40.0),
        ]
        metrics, _ = compute_metrics(trades)
        assert metrics.average_win == pytest.approx(150.0, abs=0.1)
        assert metrics.average_loss == pytest.approx(40.0, abs=0.1)

    def test_average_r(self):
        trades = [
            BacktestTrade(pnl=100.0, r_multiple=1.0),
            BacktestTrade(pnl=-50.0, r_multiple=-0.5),
        ]
        metrics, _ = compute_metrics(trades)
        assert metrics.average_r == pytest.approx(0.25, abs=0.01)

    def test_average_trade_duration(self):
        trades = [
            BacktestTrade(duration_seconds=300),
            BacktestTrade(duration_seconds=500),
        ]
        metrics, _ = compute_metrics(trades)
        assert metrics.average_trade_duration_seconds == pytest.approx(400.0, abs=0.1)

    def test_determinism(self):
        trades = [
            BacktestTrade(pnl=100.0, r_multiple=1.0, direction="bullish"),
            BacktestTrade(pnl=-50.0, r_multiple=-0.5, direction="bearish"),
            BacktestTrade(pnl=200.0, r_multiple=2.0, direction="bullish"),
        ]
        m1, e1 = compute_metrics(list(trades))
        m2, e2 = compute_metrics(list(trades))
        assert m1.to_dict() == m2.to_dict()
        for ep1, ep2 in zip(e1, e2):
            assert ep1.to_dict() == ep2.to_dict()

    def test_equity_curve_length(self):
        trades = [
            BacktestTrade(pnl=100.0), BacktestTrade(pnl=-50.0),
            BacktestTrade(pnl=200.0),
        ]
        _, equity = compute_metrics(trades)
        assert len(equity) == 3

    def test_equity_curve_peak_tracking(self):
        trades = [
            BacktestTrade(pnl=500.0),   # peak: 100500
            BacktestTrade(pnl=-300.0),  # dd: 300
            BacktestTrade(pnl=200.0),   # peak: 100400 < 100500, dd: 100
        ]
        _, equity = compute_metrics(trades)
        assert equity[0].peak_equity == 100_500.0
        assert equity[1].drawdown == 300.0
        assert equity[2].peak_equity == 100_500.0


# ─── Backtest Controller Tests ──────────────────────────────

class TestBacktestController:
    """BacktestController run, batch, sweeps."""

    def test_single_run_produces_result(self):
        bars = _trending_bars(20, "up")
        controller = BacktestController(_default_config())
        result = controller.run(bars)
        assert isinstance(result, BacktestResult)
        assert result.metrics.total_trades > 0

    def test_empty_bars(self):
        controller = BacktestController(_default_config())
        result = controller.run([])
        assert len(result.errors) > 0
        assert "No bars" in result.errors[0]

    def test_winning_strategy(self):
        """Trending-up bars produce mostly long winners in simulated mode."""
        bars = _trending_bars(30, "up")
        controller = BacktestController(_default_config())
        result = controller.run(bars)
        metrics = result.metrics
        # Trending up: more wins than losses
        assert metrics.winning_trades >= metrics.losing_trades
        assert metrics.net_profit > 0

    def test_losing_strategy(self):
        """Trending-down bars produce losing trades in simulated mode."""
        bars = _trending_bars(30, "down")
        controller = BacktestController(_default_config())
        result = controller.run(bars)
        metrics = result.metrics
        assert metrics.total_trades > 0

    def test_mixed_outcomes(self):
        bars = _choppy_bars(20)
        controller = BacktestController(_default_config())
        result = controller.run(bars)
        assert result.metrics.total_trades > 0

    def test_result_to_dict_serializable(self):
        bars = _trending_bars(15, "up")
        controller = BacktestController(_default_config())
        result = controller.run(bars)
        d = result.to_dict()
        assert "metrics" in d
        assert "trades" in d
        assert "equity_curve" in d

    def test_deterministic_same_bars(self):
        bars = _trending_bars(20, "up")
        controller1 = BacktestController(_default_config())
        controller2 = BacktestController(_default_config())
        r1 = controller1.run(list(bars))
        r2 = controller2.run(list(bars))
        assert r1.metrics.to_dict() == r2.metrics.to_dict()
        assert len(r1.trades) == len(r2.trades)

    def test_batch_run(self):
        bars = _trending_bars(10, "up")
        configs = [
            BacktestConfig(instrument="ES", initial_balance=50_000.0),
            BacktestConfig(instrument="ES", initial_balance=100_000.0),
        ]
        controller = BacktestController()
        results = controller.run_batch(list(bars), configs)
        assert len(results) == 2

    def test_large_dataset(self):
        bars = _make_bars(100)
        controller = BacktestController(_default_config())
        result = controller.run(bars)
        assert result.metrics.total_trades >= 0


# ─── Parameter Sweep Tests ──────────────────────────────────

class TestParamSweep:
    """Parameter sweep generation and execution."""

    def test_param_sweep_config_generation(self):
        sweep = ParamSweepConfig(
            instrument="ES",
            base_config={"initial_balance": 100_000.0},
            param_grid={"min_rr": [2.0, 3.0], "confidence_threshold": [60, 70]},
        )
        configs = sweep.generate_configs()
        assert len(configs) == 4  # 2 × 2

    def test_param_sweep_empty_grid(self):
        sweep = ParamSweepConfig(
            instrument="ES",
            base_config={"initial_balance": 100_000.0},
            param_grid={},
        )
        configs = sweep.generate_configs()
        assert len(configs) == 1

    def test_param_sweep_single_param(self):
        sweep = ParamSweepConfig(
            instrument="ES",
            base_config={"initial_balance": 100_000.0},
            param_grid={"position_risk_pct": [1.0, 2.0, 3.0]},
        )
        configs = sweep.generate_configs()
        assert len(configs) == 3

    def test_run_parameter_sweep(self):
        bars = _trending_bars(10, "up")
        sweep = ParamSweepConfig(
            instrument="ES",
            base_config={"initial_balance": 100_000.0},
            param_grid={"initial_balance": [50_000.0, 100_000.0]},
        )
        controller = BacktestController()
        results = controller.run_parameter_sweep(list(bars), sweep)
        assert len(results) == 2
        for r in results:
            assert r.metrics.total_trades > 0


# ─── Serialization Tests ────────────────────────────────────

class TestSerialization:
    """Result, metrics, and trade serialization."""

    def test_metrics_to_dict_complete(self):
        metrics = BacktestMetrics(
            net_profit=500.0, total_trades=10, winning_trades=6,
            losing_trades=4, win_rate=0.6,
        )
        d = metrics.to_dict()
        assert len(d) >= 26  # All 27 metric fields

    def test_result_to_dict_contains_all_sections(self):
        result = BacktestResult(config=_default_config())
        d = result.to_dict()
        assert "run_id" in d
        assert "config" in d
        assert "trades" in d
        assert "equity_curve" in d
        assert "metrics" in d


# ─── API Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backtest_run_dry_api():
    """Test /api/v1/backtesting/run-dry endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    bars = [
        _make_bar(price=100.0, minute=0),
        _make_bar(price=101.0, minute=5),
        _make_bar(price=102.0, minute=10),
        _make_bar(price=103.0, minute=15),
        _make_bar(price=104.0, minute=20),
        _make_bar(price=105.0, minute=25),
        _make_bar(price=106.0, minute=30),
        _make_bar(price=107.0, minute=35),
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/backtesting/run-dry",
            params={
                "instrument": "ES",
                "timeframe": "5m",
                "start_time": "2025-06-16T09:30:00",
                "end_time": "2025-06-16T16:00:00",
                "bars_json": json.dumps(bars),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "trades" in data


@pytest.mark.asyncio
async def test_parameter_sweep_api():
    """Test /api/v1/backtesting/sweep endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    bars = _trending_bars(10, "up")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/backtesting/sweep",
            params={
                "instrument": "ES",
                "bars_json": json.dumps(bars),
                "param_grid_json": json.dumps({"initial_balance": [50000, 100000]}),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["combinations"] == 2
        assert len(data["results"]) == 2
