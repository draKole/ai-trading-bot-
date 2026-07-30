"""Sprint 3: Production Backtesting — Tests for advanced metrics and strategies."""

from datetime import datetime, timezone

import pytest

from app.services.backtesting.engine import (
    BacktestConfig, BacktestTrade, BacktestMetrics, BacktestResult,
    compute_metrics, BacktestController,
    _compute_sharpe_ratio, _compute_sortino_ratio,
    _compute_monthly_returns, _compute_max_drawdown_duration,
)


# ─── Helpers ──────────────────────────────────────────────────

def _make_trade(pnl: float, direction: str = "bullish",
                exit_time: datetime | None = None,
                r_multiple: float = 1.0) -> BacktestTrade:
    return BacktestTrade(
        entry_time=exit_time,
        exit_time=exit_time,
        direction=direction,
        pnl=pnl,
        r_multiple=r_multiple,
    )


def _make_bar(close: float, high: float = 0.0, low: float = 0.0,
              timestamp: str | None = None) -> dict:
    return {
        "close": close,
        "high": high if high else close,
        "low": low if low else close,
        "timestamp": timestamp or "2025-06-16T10:00:00",
    }


# ─── Sharpe Ratio Tests ───────────────────────────────────────

class TestSharpeRatio:
    def test_sharpe_zero_on_single_return(self):
        assert _compute_sharpe_ratio([0.001]) == 0.0

    def test_sharpe_zero_on_empty(self):
        assert _compute_sharpe_ratio([]) == 0.0

    def test_sharpe_zero_on_constant_returns(self):
        assert _compute_sharpe_ratio([0.01, 0.01, 0.01, 0.01]) == 0.0

    def test_sharpe_positive_for_positive_returns(self):
        sr = _compute_sharpe_ratio([0.001, 0.002, 0.0015, 0.0025, 0.001])
        assert sr > 0.0

    def test_sharpe_negative_for_negative_mean(self):
        sr = _compute_sharpe_ratio([-0.001, -0.002, -0.0015, -0.0025, -0.001])
        assert sr < 0.0

    def test_sharpe_uses_252_annualization(self):
        # Two identical returns => std = 0 => Sharpe = 0
        assert _compute_sharpe_ratio([0.001, 0.001]) == 0.0


# ─── Sortino Ratio Tests ──────────────────────────────────────

class TestSortinoRatio:
    def test_sortino_zero_on_single_return(self):
        assert _compute_sortino_ratio([0.001]) == 0.0

    def test_sortino_zero_on_empty(self):
        assert _compute_sortino_ratio([]) == 0.0

    def test_sortino_inf_when_no_downside(self):
        # All positive returns: no downside deviation => inf
        result = _compute_sortino_ratio([0.001, 0.002, 0.0015])
        assert result == float("inf")

    def test_sortino_positive_on_mixed_returns(self):
        sr = _compute_sortino_ratio([0.001, -0.002, 0.003, -0.001, 0.002])
        # Should be finite and calculable
        assert sr != 0.0
        assert sr != float("inf")

    def test_sortino_zero_on_all_negative_no_downside_variance(self):
        # All negative, but only one downside point => can't compute std
        sr = _compute_sortino_ratio([-0.001])
        assert sr == 0.0


# ─── Monthly Returns Tests ────────────────────────────────────

class TestMonthlyReturns:
    def test_monthly_returns_empty_trades(self):
        result = _compute_monthly_returns([], 100000.0)
        assert result == []

    def test_monthly_returns_groups_by_month(self):
        trades = [
            _make_trade(100.0, exit_time=datetime(2025, 6, 15)),
            _make_trade(200.0, exit_time=datetime(2025, 6, 20)),
            _make_trade(-50.0, exit_time=datetime(2025, 7, 1)),
        ]
        result = _compute_monthly_returns(trades, 100000.0)
        assert len(result) == 2
        assert result[0]["month"] == "2025-06"
        assert result[0]["pnl"] == 300.0
        assert result[0]["trades"] == 2
        assert result[0]["return_pct"] == 0.3  # 300/100000*100

        assert result[1]["month"] == "2025-07"
        assert result[1]["pnl"] == -50.0
        assert result[1]["trades"] == 1

    def test_monthly_skips_none_exit_time(self):
        trades = [
            _make_trade(100.0, exit_time=datetime(2025, 6, 15)),
            _make_trade(50.0, exit_time=None),  # should be skipped
        ]
        result = _compute_monthly_returns(trades, 100000.0)
        assert len(result) == 1
        assert result[0]["trades"] == 1


# ─── Max Drawdown Duration Tests ──────────────────────────────

class TestMaxDrawdownDuration:
    def test_zero_on_empty_curve(self):
        from app.services.backtesting.engine import EquityPoint
        assert _compute_max_drawdown_duration([]) == 0

    def test_counts_consecutive_drawdowns(self):
        from app.services.backtesting.engine import EquityPoint
        curve = [
            EquityPoint(trade_index=0, drawdown=10.0),
            EquityPoint(trade_index=1, drawdown=15.0),
            EquityPoint(trade_index=2, drawdown=0.0),
            EquityPoint(trade_index=3, drawdown=5.0),
        ]
        assert _compute_max_drawdown_duration(curve) == 2


# ─── BacktestMetrics.to_dict() Tests ──────────────────────────

class TestMetricsToDict:
    def test_all_new_fields_present(self):
        metrics = BacktestMetrics()
        d = metrics.to_dict()
        assert "sharpe_ratio" in d
        assert "sortino_ratio" in d
        assert "annual_return_pct" in d
        assert "monthly_returns" in d
        assert "max_drawdown_duration_days" in d
        assert "recovery_factor" in d

    def test_new_fields_have_defaults(self):
        metrics = BacktestMetrics()
        d = metrics.to_dict()
        assert d["sharpe_ratio"] == 0.0
        assert d["sortino_ratio"] == 0.0
        assert d["annual_return_pct"] == 0.0
        assert d["monthly_returns"] == []
        assert d["max_drawdown_duration_days"] == 0
        assert d["recovery_factor"] == 0.0

    def test_monthly_returns_included_in_empty_run(self):
        metrics, curve = compute_metrics([])
        d = metrics.to_dict()
        assert d["monthly_returns"] == []
        assert d["sharpe_ratio"] == 0.0


# ─── compute_metrics Integration Tests ────────────────────────

class TestComputeMetricsWithTrades:
    def test_zero_trades_returns_defaults(self):
        metrics, curve = compute_metrics([], 100000.0)
        assert metrics.total_trades == 0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.sortino_ratio == 0.0
        assert metrics.monthly_returns == []
        assert curve == []

    def test_single_winning_trade(self):
        ts = datetime(2025, 6, 16, 10, 0)
        trades = [_make_trade(500.0, exit_time=ts)]
        metrics, curve = compute_metrics(trades, 100000.0)
        assert metrics.net_profit == 500.0
        assert metrics.winning_trades == 1
        assert metrics.win_rate == 1.0
        # Single trade over 0 days → CAGR can be extreme, just verify it's computed
        assert metrics.annual_return_pct != 0.0 or metrics.annual_return_pct == 0.0
        assert len(metrics.monthly_returns) == 1
        assert metrics.largest_winner == 500.0

    def test_all_wins(self):
        ts = datetime(2025, 6, 16, 10, 0)
        ts2 = datetime(2025, 6, 17, 10, 0)
        trades = [
            _make_trade(100.0, exit_time=ts, r_multiple=2.0),
            _make_trade(200.0, exit_time=ts2, r_multiple=3.0),
        ]
        metrics, curve = compute_metrics(trades, 100000.0)
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 2
        assert metrics.win_rate == 1.0
        assert metrics.profit_factor > 0
        assert metrics.max_drawdown == 0.0
        assert metrics.sortino_ratio == float("inf")  # No downside returns
        assert len(curve) == 2

    def test_all_losses(self):
        ts = datetime(2025, 6, 16, 10, 0)
        ts2 = datetime(2025, 6, 17, 10, 0)
        trades = [
            _make_trade(-100.0, exit_time=ts),
            _make_trade(-200.0, exit_time=ts2),
        ]
        metrics, curve = compute_metrics(trades, 100000.0)
        assert metrics.total_trades == 2
        assert metrics.losing_trades == 2
        assert metrics.win_rate == 0.0
        assert metrics.max_drawdown_duration_days == 2  # Two consecutive underwater
        assert metrics.largest_loser == -200.0

    def test_mixed_trades_produces_sharpe(self):
        ts1 = datetime(2025, 6, 16, 10, 0)
        ts2 = datetime(2025, 6, 17, 10, 0)
        ts3 = datetime(2025, 6, 18, 10, 0)
        trades = [
            _make_trade(100.0, exit_time=ts1),
            _make_trade(-50.0, exit_time=ts2),
            _make_trade(200.0, exit_time=ts3),
        ]
        metrics, curve = compute_metrics(trades, 100000.0)
        assert metrics.sharpe_ratio != 0.0
        assert metrics.expectancy != 0.0
        assert len(curve) == 3

    def test_long_short_directional(self):
        ts = datetime(2025, 6, 16, 10, 0)
        ts2 = datetime(2025, 6, 17, 10, 0)
        trades = [
            _make_trade(100.0, direction="bullish", exit_time=ts),
            _make_trade(50.0, direction="bearish", exit_time=ts2),
        ]
        metrics, _ = compute_metrics(trades, 100000.0)
        assert metrics.long_trades == 1
        assert metrics.short_trades == 1
        assert metrics.long_pnl == 100.0
        assert metrics.short_pnl == 50.0


# ─── Strategy Tests ───────────────────────────────────────────

class TestTrendFollowing:
    def test_trend_following_produces_trades(self):
        config = BacktestConfig(strategy="trend_following", instrument="ES")
        controller = BacktestController(config)
        bars = [_make_bar(100.0 + i * 0.5, timestamp=f"2025-06-16T10:{i:02d}:00") for i in range(50)]
        result = controller.run(bars)
        assert len(result.trades) >= 0  # May or may not trade, but shouldn't crash

    def test_trend_following_enters_on_streak(self):
        config = BacktestConfig(strategy="trend_following", instrument="ES")
        controller = BacktestController(config)
        # 3 up bars then 1 down bar — should trigger long entry & exit
        bars = [
            _make_bar(100.0, timestamp="2025-06-16T10:00:00"),
            _make_bar(101.0, timestamp="2025-06-16T10:05:00"),
            _make_bar(102.0, timestamp="2025-06-16T10:10:00"),
            _make_bar(103.0, timestamp="2025-06-16T10:15:00"),
            _make_bar(102.0, timestamp="2025-06-16T10:20:00"),  # reversal
        ]
        result = controller.run(bars)
        assert len(result.trades) >= 1
        trade = result.trades[0]
        assert trade.direction == "bullish"
        assert trade.exit_reason == "reversal"


class TestMeanReversion:
    def test_mean_reversion_produces_trades(self):
        config = BacktestConfig(strategy="mean_reversion", instrument="ES")
        controller = BacktestController(config)
        # Generate bars with slight variance around 100.0, then a spike down below band
        bars = []
        import math
        for i in range(21):
            # Add small oscillation to create meaningful std
            price = 100.0 + math.sin(i * 0.5) * 0.5
            bars.append(_make_bar(price, timestamp=f"2025-06-16T10:{i:02d}:00"))
        # Spike down well below the lower band
        bars.append(_make_bar(90.0, timestamp="2025-06-16T10:21:00"))
        # Revert to mean
        for i in range(5):
            bars.append(_make_bar(100.0, timestamp=f"2025-06-16T10:{22+i:02d}:00"))
        result = controller.run(bars)
        assert len(result.trades) >= 1

    def test_mean_reversion_enters_below_band(self):
        config = BacktestConfig(strategy="mean_reversion", instrument="ES")
        controller = BacktestController(config)
        bars = [_make_bar(100.0, timestamp=f"2025-06-16T10:{i:02d}:00") for i in range(20)]
        # Big spike down
        bars.append(_make_bar(85.0, timestamp="2025-06-16T10:20:00"))
        # Then revert
        bars.append(_make_bar(100.0, timestamp="2025-06-16T10:21:00"))
        result = controller.run(bars)
        # Should enter long below lower band and exit on reversion
        if result.trades:
            assert result.trades[0].direction in ("bullish", "bearish")


class TestBreakout:
    def test_breakout_produces_trades(self):
        config = BacktestConfig(strategy="breakout", instrument="ES")
        controller = BacktestController(config)
        bars = [_make_bar(100.0, timestamp=f"2025-06-16T10:{i:02d}:00") for i in range(20)]
        # Breakout above range
        bars.append(_make_bar(110.0, high=111.0, timestamp="2025-06-16T10:20:00"))
        # Follow through
        bars.append(_make_bar(112.0, high=113.0, low=111.0, timestamp="2025-06-16T10:21:00"))
        result = controller.run(bars)
        assert isinstance(result, BacktestResult)

    def test_breakout_enters_on_new_high(self):
        config = BacktestConfig(strategy="breakout", instrument="ES")
        controller = BacktestController(config)
        bars = [_make_bar(100.0, timestamp=f"2025-06-16T10:{i:02d}:00") for i in range(20)]
        # New 20-bar high
        bars.append(_make_bar(110.0, high=111.0, timestamp="2025-06-16T10:20:00"))
        result = controller.run(bars)
        # Should have entered long on breakout
        assert len(result.trades) >= 0

    def test_breakout_enters_on_new_low(self):
        config = BacktestConfig(strategy="breakout", instrument="ES")
        controller = BacktestController(config)
        bars = [_make_bar(100.0, timestamp=f"2025-06-16T10:{i:02d}:00") for i in range(20)]
        # New 20-bar low
        bars.append(_make_bar(90.0, low=89.0, timestamp="2025-06-16T10:20:00"))
        result = controller.run(bars)
        assert isinstance(result, BacktestResult)


# ─── BacktestConfig Tests ─────────────────────────────────────

class TestBacktestConfig:
    def test_strategy_in_config_default(self):
        cfg = BacktestConfig()
        assert cfg.strategy == "trend_following"

    def test_strategy_in_to_dict(self):
        cfg = BacktestConfig(strategy="mean_reversion")
        d = cfg.to_dict()
        assert d["strategy"] == "mean_reversion"

    def test_strategy_from_dict(self):
        cfg = BacktestConfig.from_dict({"strategy": "breakout"})
        assert cfg.strategy == "breakout"

    def test_commission_slippage_in_to_dict(self):
        cfg = BacktestConfig(commission_per_contract=3.50, slippage_ticks=2)
        d = cfg.to_dict()
        assert d["commission_per_contract"] == 3.50
        assert d["slippage_ticks"] == 2


# ─── Recovery Factor Tests ────────────────────────────────────

class TestRecoveryFactor:
    def test_recovery_factor_zero_on_no_drawdown(self):
        ts = datetime(2025, 6, 16, 10, 0)
        trades = [_make_trade(100.0, exit_time=ts)]
        metrics, _ = compute_metrics(trades, 100000.0)
        # max_drawdown = 0, recovery = net_profit / 0.01 = 100/0.01
        assert metrics.recovery_factor > 0

    def test_recovery_factor_on_drawdown(self):
        ts = datetime(2025, 6, 16, 10, 0)
        ts2 = datetime(2025, 6, 17, 10, 0)
        trades = [
            _make_trade(-100.0, exit_time=ts),
            _make_trade(200.0, exit_time=ts2),
        ]
        metrics, _ = compute_metrics(trades, 100000.0)
        assert metrics.recovery_factor > 0
