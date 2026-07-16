"""Backtesting Engine — replay historical data through the pipeline.

Reproducible, look-ahead-bias-free. Supports in-sample/out-of-sample
split and walk-forward testing.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BacktestConfig:
    instrument: str
    start_date: datetime
    end_date: datetime
    strategy_version: str
    timeframes: list[str] = field(default_factory=lambda: ["5m", "15m", "1h"])
    risk_profile: str = "default"
    initial_balance: float = 100_000.0
    commission_per_contract: float = 2.50
    slippage_ticks: int = 1


@dataclass
class BacktestResult:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    win_rate: float = 0.0
    avg_winner_r: float = 0.0
    avg_loser_r: float = 0.0
    expectancy: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    sharpe_ratio: float | None = None


class BacktestingEngine:
    """Replay historical data through the full trading pipeline.

    Not yet implemented — interface defined for Phase 4.
    """
    pass
