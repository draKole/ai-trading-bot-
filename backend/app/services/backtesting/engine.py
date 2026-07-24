"""Backtesting Engine — deterministic strategy evaluation over historical data.

Wraps the Phase 5A ReplayController to replay historical bars through the
engine pipeline, collect completed trades, and compute performance metrics.

All metric calculations are deterministic. No duplicate replay logic.
"""

from __future__ import annotations

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

    def to_dict(self) -> dict:
        return {
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
        }


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

    for i, trade in enumerate(trades):
        pnl = trade.pnl

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

    # Fill metrics
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

    return metrics, equity_curve


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
        """Simplified simulation — trades from price movements.

        A basic trend-following simulation for testing metric calculations.
        Opens long when price rises 3 bars in a row, exits on reversal.
        """
        trades: list[BacktestTrade] = []
        in_trade = False
        entry_bar: dict | None = None
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
                # Enter long
                in_trade = True
                entry_bar = bar
                entry_price = close
                direction = "bullish"
            elif not in_trade and down_streak >= 3:
                # Enter short
                in_trade = True
                entry_bar = bar
                entry_price = close
                direction = "bearish"
            elif in_trade:
                # Check exit
                exit_signal = False
                exit_reason = ""
                if direction == "bullish" and down_streak >= 1:
                    exit_signal = True
                    exit_reason = "reversal"
                elif direction == "bearish" and up_streak >= 1:
                    exit_signal = True
                    exit_reason = "reversal"

                # Force exit on last bar
                if i == len(bars) - 1:
                    exit_signal = True
                    exit_reason = "end_of_data"

                if exit_signal and entry_bar:
                    pnl = 0.0
                    risk = float(bar.get("high", close)) - float(bar.get("low", close))
                    if risk <= 0:
                        risk = close * 0.01

                    if direction == "bullish":
                        pnl = (close - entry_price) * self.config.initial_balance * 0.001 / entry_price
                        r_mult = (close - entry_price) / risk
                    else:
                        pnl = (entry_price - close) * self.config.initial_balance * 0.001 / entry_price
                        r_mult = (entry_price - close) / risk

                    entry_ts = bar.get("timestamp")
                    if isinstance(entry_ts, str):
                        entry_ts = datetime.fromisoformat(entry_ts)

                    exit_ts = bar.get("timestamp")
                    if isinstance(exit_ts, str):
                        exit_ts = datetime.fromisoformat(exit_ts)

                    duration = 0
                    if entry_ts and exit_ts:
                        duration = int((exit_ts - entry_ts).total_seconds())

                    trades.append(BacktestTrade(
                        entry_time=entry_ts,
                        exit_time=exit_ts,
                        direction=direction,
                        entry_price=entry_price,
                        exit_price=close,
                        stop_price=entry_price * 0.99 if direction == "bullish" else entry_price * 1.01,
                        risk=round(risk, 4),
                        r_multiple=round(r_mult, 4),
                        pnl=round(pnl, 2),
                        duration_seconds=duration,
                        exit_reason=exit_reason,
                    ))

                    in_trade = False
                    entry_bar = None
                    up_streak = 0
                    down_streak = 0

        result.trades = trades
        result.metrics, result.equity_curve = compute_metrics(
            trades, self.config.initial_balance,
        )
        return result

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
