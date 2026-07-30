"""Backtesting Engine — deterministic strategy evaluation over historical data.

Wraps the Phase 5A ReplayController to replay historical bars through the
engine pipeline, collect completed trades, and compute performance metrics.

All metric calculations are deterministic. No duplicate replay logic.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4


# ─── Config ───────────────────────────────────────────────────

@dataclass
class BacktestConfig:
    """Configuration for a backtesting run."""
    instrument: str = ""
    timeframe: str = "5m"
    start_time: datetime | None = None
    end_time: datetime | None = None
    replay_mode: str = "candle_by_candle"
    strategy: str = "trend_following"  # trend_following, mean_reversion, breakout
    strategy_params: dict = field(default_factory=dict)
    initial_balance: float = 100_000.0
    commission_per_contract: float = 2.50
    slippage_ticks: int = 1

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "replay_mode": self.replay_mode,
            "strategy": self.strategy,
            "strategy_params": self.strategy_params,
            "initial_balance": self.initial_balance,
            "commission_per_contract": self.commission_per_contract,
            "slippage_ticks": self.slippage_ticks,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BacktestConfig:
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        for key in ("start_time", "end_time"):
            if key in valid and isinstance(valid[key], str):
                valid[key] = datetime.fromisoformat(valid[key])
        return cls(**valid)


# ─── Parameter Sweep Config ──────────────────────────────────

@dataclass
class ParamSweepConfig:
    """Configuration for a parameter sweep across multiple backtest runs."""
    instrument: str = ""
    timeframe: str = "5m"
    start_time: datetime | None = None
    end_time: datetime | None = None
    base_config: dict = field(default_factory=dict)
    param_grid: dict[str, list] = field(default_factory=dict)

    def generate_configs(self) -> list[BacktestConfig]:
        """Generate all config combinations from param_grid."""
        keys = list(self.param_grid.keys())
        if not keys:
            return [BacktestConfig.from_dict(self.base_config)]

        configs: list[BacktestConfig] = []
        self._recurse(keys, 0, {}, configs)
        return configs

    def _recurse(self, keys: list[str], idx: int,
                 current: dict, results: list[BacktestConfig]) -> None:
        if idx >= len(keys):
            merged = {**self.base_config, **current}
            merged["instrument"] = self.instrument
            merged["timeframe"] = self.timeframe
            if self.start_time:
                merged["start_time"] = self.start_time
            if self.end_time:
                merged["end_time"] = self.end_time
            results.append(BacktestConfig.from_dict(merged))
            return
        key = keys[idx]
        for value in self.param_grid[key]:
            current[key] = value
            self._recurse(keys, idx + 1, current, results)
            del current[key]


# ─── Trade Record ────────────────────────────────────────────

@dataclass
class BacktestTrade:
    """A single completed trade in a backtest."""
    trade_id: str = field(default_factory=lambda: str(uuid4()))
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    direction: str = ""
    quantity: int = 1
    entry_price: float = 0.0
    exit_price: float = 0.0
    stop_price: float = 0.0
    risk: float = 0.0
    r_multiple: float = 0.0
    pnl: float = 0.0
    duration_seconds: int = 0
    exit_reason: str = ""
    strategy_version: str = "1.0.0"

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "direction": self.direction,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "stop_price": self.stop_price,
            "risk": round(self.risk, 4),
            "r_multiple": round(self.r_multiple, 4),
            "pnl": round(self.pnl, 2),
            "duration_seconds": self.duration_seconds,
            "exit_reason": self.exit_reason,
            "strategy_version": self.strategy_version,
        }


# ─── Equity Point ────────────────────────────────────────────

@dataclass
class EquityPoint:
    """Single point on the equity curve after a closed trade."""
    trade_index: int
    timestamp: datetime | None = None
    account_balance: float = 0.0
    equity: float = 0.0
    drawdown: float = 0.0
    drawdown_pct: float = 0.0
    peak_equity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "trade_index": self.trade_index,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "account_balance": round(self.account_balance, 2),
            "equity": round(self.equity, 2),
            "drawdown": round(self.drawdown, 2),
            "drawdown_pct": round(self.drawdown_pct, 4),
            "peak_equity": round(self.peak_equity, 2),
        }


# ─── Backtest Metrics ────────────────────────────────────────

@dataclass
class BacktestMetrics:
    """All performance metrics computed from a list of trades."""

    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    win_rate: float = 0.0
    loss_rate: float = 0.0

    profit_factor: float = 0.0

    average_win: float = 0.0
    average_loss: float = 0.0
    average_r: float = 0.0

    expectancy: float = 0.0

    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0

    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    average_trade_duration_seconds: float = 0.0

    long_trades: int = 0
    long_wins: int = 0
    long_pnl: float = 0.0
    short_trades: int = 0
    short_wins: int = 0
    short_pnl: float = 0.0

    largest_winner: float = 0.0
    largest_loser: float = 0.0

    # Sprint 3 — advanced metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    annual_return_pct: float = 0.0
    monthly_returns: list[dict] = field(default_factory=list)
    max_drawdown_duration_days: int = 0
    recovery_factor: float = 0.0

    def to_dict(self) -> dict:
        result = {
            "net_profit": round(self.net_profit, 2),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "breakeven_trades": self.breakeven_trades,
            "win_rate": round(self.win_rate, 4),
            "loss_rate": round(self.loss_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "average_win": round(self.average_win, 2),
            "average_loss": round(self.average_loss, 2),
            "average_r": round(self.average_r, 4),
            "expectancy": round(self.expectancy, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "average_trade_duration_seconds": round(self.average_trade_duration_seconds, 1),
            "long_trades": self.long_trades,
            "long_wins": self.long_wins,
            "long_pnl": round(self.long_pnl, 2),
            "short_trades": self.short_trades,
            "short_wins": self.short_wins,
            "short_pnl": round(self.short_pnl, 2),
            "largest_winner": round(self.largest_winner, 2),
            "largest_loser": round(self.largest_loser, 2),
            # Sprint 3
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "annual_return_pct": round(self.annual_return_pct, 2),
            "monthly_returns": self.monthly_returns,
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "recovery_factor": round(self.recovery_factor, 4),
        }
        return result


# ─── Backtest Result ─────────────────────────────────────────

@dataclass
class BacktestResult:
    """Complete result from a backtest run."""
    run_id: str = field(default_factory=lambda: str(uuid4()))
    config: BacktestConfig = field(default_factory=BacktestConfig)
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "config": self.config.to_dict(),
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": [e.to_dict() for e in self.equity_curve],
            "metrics": self.metrics.to_dict(),
            "errors": self.errors,
        }


# ─── Metric Calculator ───────────────────────────────────────

def _compute_sharpe_ratio(daily_returns: list[float], trading_days: int = 252) -> float:
    """Annualized Sharpe ratio: sqrt(252) * mean(daily) / std(daily)."""
    if len(daily_returns) < 2:
        return 0.0
    mean_r = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std_r = math.sqrt(variance)
    if std_r == 0.0:
        return 0.0
    return (mean_r / std_r) * math.sqrt(trading_days)


def _compute_sortino_ratio(daily_returns: list[float], trading_days: int = 252) -> float:
    """Annualized Sortino ratio: only downside deviation (returns < 0)."""
    if len(daily_returns) < 2:
        return 0.0
    mean_r = sum(daily_returns) / len(daily_returns)
    downside = [r for r in daily_returns if r < 0]
    if len(downside) < 2:
        return 0.0 if mean_r <= 0 else float("inf")
    ds_mean = sum(downside) / len(downside)
    ds_variance = sum((r - ds_mean) ** 2 for r in downside) / (len(downside) - 1)
    ds_std = math.sqrt(ds_variance)
    if ds_std == 0.0:
        return 0.0
    return (mean_r / ds_std) * math.sqrt(trading_days)


def _compute_monthly_returns(
    trades: list[BacktestTrade], initial_balance: float,
) -> list[dict]:
    """Group trades by calendar month and compute monthly return stats."""
    monthly: dict[str, dict] = defaultdict(lambda: {
        "pnl": 0.0, "trades": 0, "month": "",
    })

    for t in trades:
        if t.exit_time is None:
            continue
        key = t.exit_time.strftime("%Y-%m")
        entry = monthly[key]
        entry["month"] = key
        entry["pnl"] += t.pnl
        entry["trades"] += 1

    result = []
    for key in sorted(monthly.keys()):
        m = monthly[key]
        m["return_pct"] = round((m["pnl"] / initial_balance) * 100, 4) if initial_balance > 0 else 0.0
        m["pnl"] = round(m["pnl"], 2)
        result.append(m)

    return result


def _compute_max_drawdown_duration(equity_curve: list[EquityPoint]) -> int:
    """Longest consecutive period (in days) where equity was below peak."""
    if not equity_curve:
        return 0

    max_duration = 0
    current_duration = 0

    for ep in equity_curve:
        if ep.drawdown > 0:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0

    return max_duration


def compute_metrics(trades: list[BacktestTrade],
                    initial_balance: float = 100_000.0) -> tuple[BacktestMetrics, list[EquityPoint]]:
    """Compute all performance metrics from a list of trades.

    Deterministic: same trade list → same metrics every time.

    Returns (metrics, equity_curve).
    """
    metrics = BacktestMetrics()
    equity_curve: list[EquityPoint] = []

    if not trades:
        return metrics, equity_curve

    # Counters and accumulators
    total_pnl = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    wins = 0
    losses = 0
    breakevens = 0
    total_r = 0.0
    total_duration = 0.0

    current_wins = 0
    current_losses = 0
    max_wins = 0
    max_losses = 0

    balance = initial_balance
    peak_equity = initial_balance
    max_dd = 0.0
    max_dd_pct = 0.0

    long_trades = 0
    long_wins = 0
    long_pnl = 0.0
    short_trades = 0
    short_wins = 0
    short_pnl = 0.0

    largest_winner = 0.0
    largest_loser = 0.0

    # Sprint 3 — daily returns tracking
    daily_pnl: dict[str, float] = defaultdict(float)

    for i, trade in enumerate(trades):
        pnl = trade.pnl

        # Daily PnL grouping for Sharpe/Sortino
        if trade.exit_time:
            day_key = trade.exit_time.strftime("%Y-%m-%d")
            daily_pnl[day_key] += pnl

        # Core metrics
        total_pnl += pnl
        if pnl > 0:
            gross_profit += pnl
            wins += 1
            current_wins += 1
            current_losses = 0
            largest_winner = max(largest_winner, pnl)
        elif pnl < 0:
            gross_loss += abs(pnl)
            losses += 1
            current_losses += 1
            current_wins = 0
            largest_loser = min(largest_loser, pnl)
        else:
            breakevens += 1
            current_wins = 0
            current_losses = 0

        max_wins = max(max_wins, current_wins)
        max_losses = max(max_losses, current_losses)
        total_r += trade.r_multiple
        total_duration += trade.duration_seconds

        # Directional
        if trade.direction == "bullish":
            long_trades += 1
            long_pnl += pnl
            if pnl > 0:
                long_wins += 1
        elif trade.direction == "bearish":
            short_trades += 1
            short_pnl += pnl
            if pnl > 0:
                short_wins += 1

        # Equity curve
        balance += pnl
        peak_equity = max(peak_equity, balance)
        dd = peak_equity - balance
        dd_pct = (dd / peak_equity * 100) if peak_equity > 0 else 0.0
        max_dd = max(max_dd, dd)
        max_dd_pct = max(max_dd_pct, dd_pct)

        equity_curve.append(EquityPoint(
            trade_index=i,
            timestamp=trade.exit_time,
            account_balance=round(balance, 2),
            equity=round(balance, 2),
            drawdown=round(dd, 2),
            drawdown_pct=round(dd_pct, 4),
            peak_equity=round(peak_equity, 2),
        ))

    total = wins + losses + breakevens

    # Fill base metrics
    metrics.net_profit = round(total_pnl, 2)
    metrics.gross_profit = round(gross_profit, 2)
    metrics.gross_loss = round(gross_loss, 2)
    metrics.total_trades = total
    metrics.winning_trades = wins
    metrics.losing_trades = losses
    metrics.breakeven_trades = breakevens
    metrics.win_rate = round(wins / max(total, 1), 4)
    metrics.loss_rate = round(losses / max(total, 1), 4)
    metrics.profit_factor = round(gross_profit / max(gross_loss, 0.01), 4)
    metrics.average_win = round(gross_profit / max(wins, 1), 2)
    metrics.average_loss = round(gross_loss / max(losses, 1), 2)
    metrics.average_r = round(total_r / max(total, 1), 4)
    metrics.expectancy = round(
        (metrics.win_rate * metrics.average_win) -
        (metrics.loss_rate * metrics.average_loss), 2,
    )
    metrics.max_drawdown = round(max_dd, 2)
    metrics.max_drawdown_pct = round(max_dd_pct, 4)
    metrics.max_consecutive_wins = max_wins
    metrics.max_consecutive_losses = max_losses
    metrics.average_trade_duration_seconds = round(
        total_duration / max(total, 1), 1,
    )
    metrics.long_trades = long_trades
    metrics.long_wins = long_wins
    metrics.long_pnl = round(long_pnl, 2)
    metrics.short_trades = short_trades
    metrics.short_wins = short_wins
    metrics.short_pnl = round(short_pnl, 2)
    metrics.largest_winner = round(largest_winner, 2)
    metrics.largest_loser = round(largest_loser, 2)

    # Sprint 3 — advanced metrics
    daily_returns = [daily_pnl[k] / initial_balance for k in sorted(daily_pnl.keys())]
    metrics.sharpe_ratio = round(_compute_sharpe_ratio(daily_returns), 4)
    metrics.sortino_ratio = round(_compute_sortino_ratio(daily_returns), 4)

    # Annual return (CAGR approximation)
    trading_days = _estimate_trading_days(trades)
    if trades and trading_days > 0:
        final_balance = initial_balance + total_pnl
        if initial_balance > 0 and final_balance > 0:
            metrics.annual_return_pct = round(
                ((final_balance / initial_balance) ** (252.0 / trading_days) - 1) * 100, 2,
            )

    metrics.monthly_returns = _compute_monthly_returns(trades, initial_balance)
    metrics.max_drawdown_duration_days = _compute_max_drawdown_duration(equity_curve)
    metrics.recovery_factor = round(
        abs(metrics.net_profit / max(metrics.max_drawdown, 0.01)), 4,
    )

    return metrics, equity_curve


def _estimate_trading_days(trades: list[BacktestTrade]) -> int:
    """Estimate number of trading days spanned by the trade list."""
    if not trades:
        return 0
    timestamps = [t.exit_time for t in trades if t.exit_time is not None]
    if not timestamps:
        return 0
    return max(1, (max(timestamps) - min(timestamps)).days)


# ─── Backtest Controller ─────────────────────────────────────

class BacktestController:
    """Orchestrates replay sessions and analyzes resulting trades.

    Wraps ReplayController — does NOT duplicate replay logic.
    """

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    def run(self, bars: list[dict],
            replay_controller=None) -> BacktestResult:
        """Run a single backtest over the provided bars.

        Uses the ReplayController to feed bars through the engine pipeline,
        then collects completed trades from replay snapshots.

        If replay_controller is None, runs in a simplified mode where
        trades are simulated from bar data directly (for testing).
        """
        result = BacktestResult(config=self.config)

        if not bars:
            result.errors.append("No bars provided")
            return result

        if replay_controller is not None:
            return self._run_with_replay(bars, replay_controller, result)

        # Simplified mode: simulate trades from price movements
        return self._run_simulated(bars, result)

    def _run_with_replay(self, bars: list[dict],
                         replay_controller, result: BacktestResult) -> BacktestResult:
        """Run using the ReplayController (full pipeline)."""
        from app.services.replay.engine import ReplayConfig, OHLCVBar

        rc_config = ReplayConfig(
            instrument=self.config.instrument,
            timeframe=self.config.timeframe,
            start_time=self.config.start_time,
            end_time=self.config.end_time,
            mode=self.config.replay_mode,
        )
        replay_controller.reset()
        replay_controller.config = rc_config

        ob_bars = [OHLCVBar.from_dict(b) for b in bars]
        replay_controller.load_bars(ob_bars)
        snapshots = replay_controller.dry_run()

        trades = self._extract_trades_from_snapshots(snapshots)
        result.trades = trades
        result.metrics, result.equity_curve = compute_metrics(
            trades, self.config.initial_balance,
        )
        return result

    def _run_simulated(self, bars: list[dict],
                       result: BacktestResult) -> BacktestResult:
        """Dispatch to the selected strategy."""
        strategy = self.config.strategy
        if strategy == "mean_reversion":
            return self._run_mean_reversion(bars, result)
        elif strategy == "breakout":
            return self._run_breakout(bars, result)
        else:
            return self._run_trend_following(bars, result)

    def _run_trend_following(self, bars: list[dict],
                             result: BacktestResult) -> BacktestResult:
        """Trend-following: enters on 3-bar streak, exits on reversal."""
        trades: list[BacktestTrade] = []
        in_trade = False
        entry_price = 0.0
        direction = "bullish"
        up_streak = 0
        down_streak = 0

        for i, bar in enumerate(bars):
            close = float(bar.get("close", 0))

            if i > 0:
                prev_close = float(bars[i - 1].get("close", 0))
                if close > prev_close:
                    up_streak += 1
                    down_streak = 0
                elif close < prev_close:
                    down_streak += 1
                    up_streak = 0
                else:
                    up_streak = 0
                    down_streak = 0

            if not in_trade and up_streak >= 3:
                in_trade = True
                entry_price = close
                direction = "bullish"
            elif not in_trade and down_streak >= 3:
                in_trade = True
                entry_price = close
                direction = "bearish"
            elif in_trade:
                exit_signal = False
                exit_reason = ""
                if direction == "bullish" and down_streak >= 1:
                    exit_signal = True
                    exit_reason = "reversal"
                elif direction == "bearish" and up_streak >= 1:
                    exit_signal = True
                    exit_reason = "reversal"

                # Force exit on last bar — but don't override a real exit reason
                if i == len(bars) - 1 and not exit_signal:
                    exit_signal = True
                    exit_reason = "end_of_data"
                elif i == len(bars) - 1 and exit_signal:
                    pass  # Keep the existing exit_reason

                if exit_signal:
                    trade = self._create_trade(bar, entry_price, close, direction, exit_reason)
                    trades.append(trade)
                    in_trade = False
                    up_streak = 0
                    down_streak = 0

        result.trades = trades
        result.metrics, result.equity_curve = compute_metrics(
            trades, self.config.initial_balance,
        )
        return result

    def _run_mean_reversion(self, bars: list[dict],
                            result: BacktestResult) -> BacktestResult:
        """Mean reversion: enter when price crosses below lower Bollinger band
        (2 std below 20-bar SMA), exit on reversion to mean (SMA)."""
        trades: list[BacktestTrade] = []
        lookback = 20
        in_trade = False
        entry_price = 0.0
        direction = ""

        closes = [float(b.get("close", 0)) for b in bars]

        for i in range(lookback, len(bars)):
            window = closes[i - lookback:i]
            sma = sum(window) / lookback
            variance = sum((c - sma) ** 2 for c in window) / lookback
            std = math.sqrt(variance)
            lower_band = sma - 2 * std
            upper_band = sma + 2 * std if std > 0 else sma

            close_i = closes[i]
            bar = bars[i]

            if not in_trade:
                # Enter long when price crosses below lower band
                if close_i < lower_band and std > 0:
                    in_trade = True
                    entry_price = close_i
                    direction = "bullish"
                # Enter short when price crosses above upper band
                elif close_i > upper_band and std > 0:
                    in_trade = True
                    entry_price = close_i
                    direction = "bearish"
            else:
                exit_signal = False
                exit_reason = ""
                # Exit long on reversion to mean
                if direction == "bullish" and close_i >= sma:
                    exit_signal = True
                    exit_reason = "reversion_to_mean"
                # Exit short on reversion to mean
                elif direction == "bearish" and close_i <= sma:
                    exit_signal = True
                    exit_reason = "reversion_to_mean"

                if i == len(bars) - 1 and in_trade:
                    exit_signal = True
                    exit_reason = "end_of_data"

                if exit_signal:
                    trade = self._create_trade(bar, entry_price, close_i, direction, exit_reason)
                    trades.append(trade)
                    in_trade = False

        result.trades = trades
        result.metrics, result.equity_curve = compute_metrics(
            trades, self.config.initial_balance,
        )
        return result

    def _run_breakout(self, bars: list[dict],
                      result: BacktestResult) -> BacktestResult:
        """Breakout: enter long on new 20-bar high, short on new 20-bar low."""
        trades: list[BacktestTrade] = []
        lookback = 20
        in_trade = False
        entry_price = 0.0
        direction = ""

        highs = [float(b.get("high", float(b.get("close", 0)))) for b in bars]
        lows = [float(b.get("low", float(b.get("close", 0)))) for b in bars]
        closes = [float(b.get("close", 0)) for b in bars]

        for i in range(lookback, len(bars)):
            high_i = highs[i]
            low_i = lows[i]
            bar = bars[i]

            # Compute 20-bar high/low excluding current bar
            prev_high = max(highs[i - lookback:i])
            prev_low = min(lows[i - lookback:i])

            if not in_trade:
                # Enter long on new high breakout
                if high_i > prev_high:
                    in_trade = True
                    entry_price = high_i
                    direction = "bullish"
                # Enter short on new low breakdown
                elif low_i < prev_low:
                    in_trade = True
                    entry_price = low_i
                    direction = "bearish"
            else:
                exit_signal = False
                exit_reason = ""
                # Exit on opposite breakout
                if direction == "bullish" and low_i < prev_low:
                    exit_signal = True
                    exit_reason = "breakdown"
                elif direction == "bearish" and high_i > prev_high:
                    exit_signal = True
                    exit_reason = "breakout"

                if i == len(bars) - 1 and in_trade:
                    exit_signal = True
                    exit_reason = "end_of_data"

                if exit_signal:
                    exit_price = closes[i]
                    trade = self._create_trade(bar, entry_price, exit_price, direction, exit_reason)
                    trades.append(trade)
                    in_trade = False

        result.trades = trades
        result.metrics, result.equity_curve = compute_metrics(
            trades, self.config.initial_balance,
        )
        return result

    def _create_trade(self, bar: dict, entry_price: float, exit_price: float,
                      direction: str, exit_reason: str) -> BacktestTrade:
        """Create a BacktestTrade from bar data, entry/exit prices, and direction."""
        close = float(bar.get("close", exit_price))
        risk = float(bar.get("high", close)) - float(bar.get("low", close))
        if risk <= 0:
            risk = close * 0.01

        if direction == "bullish":
            pnl = (exit_price - entry_price) * self.config.initial_balance * 0.001 / entry_price
            r_mult = (exit_price - entry_price) / risk
        else:
            pnl = (entry_price - exit_price) * self.config.initial_balance * 0.001 / entry_price
            r_mult = (entry_price - exit_price) / risk

        ts = bar.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)

        return BacktestTrade(
            entry_time=ts,
            exit_time=ts,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_price=entry_price * 0.99 if direction == "bullish" else entry_price * 1.01,
            risk=round(risk, 4),
            r_multiple=round(r_mult, 4),
            pnl=round(pnl, 2),
            duration_seconds=0,
            exit_reason=exit_reason,
        )

    def _extract_trades_from_snapshots(self,
                                        snapshots: list) -> list[BacktestTrade]:
        """Extract completed trades from replay snapshots."""
        trades: list[BacktestTrade] = []
        for snap in snapshots:
            d = snap.to_dict() if hasattr(snap, 'to_dict') else snap
            mgmt_ref = d.get("trade_mgmt_state_ref", "")
            if mgmt_ref and "exited" in str(mgmt_ref).lower():
                # Extract trade details from snapshot
                candles = d.get("candle", {})
                trades.append(BacktestTrade(
                    entry_time=None,
                    exit_time=snap.current_timestamp if hasattr(snap, 'current_timestamp') else None,
                    direction=d.get("market_bias", {}).get("direction", "bullish"),
                    pnl=0.0,
                    exit_reason=d.get("trade_mgmt_state_ref", ""),
                ))
        return trades

    def run_batch(self, bars: list[dict],
                  configs: list[BacktestConfig]) -> list[BacktestResult]:
        """Run multiple backtests with different configs."""
        results: list[BacktestResult] = []
        for cfg in configs:
            self.config = cfg
            result = self.run(list(bars))  # Fresh copy
            results.append(result)
        return results

    def run_parameter_sweep(self, bars: list[dict],
                            sweep: ParamSweepConfig) -> list[BacktestResult]:
        """Run a parameter sweep — one result per combination."""
        configs = sweep.generate_configs()
        return self.run_batch(bars, configs)
