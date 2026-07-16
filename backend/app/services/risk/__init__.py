"""Risk Engine — the final gatekeeper.

Sits between signal generation and order placement.
Has veto power over EVERY trade, regardless of confluence score.
Stateless per check — reads current account state from DB/Redis.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RiskDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class RiskProfile:
    """Configurable risk profile (default, prop-firm-specific, etc.)."""
    name: str
    risk_per_trade_pct: float = 0.01
    max_daily_loss_pct: float = 0.03
    max_trailing_drawdown_pct: float = 0.05
    max_contracts: int = 10
    max_trades_per_day: int = 10
    max_trades_per_session: int = 5
    max_consecutive_losses: int = 3
    min_risk_reward: float = 2.0
    stale_signal_seconds: int = 300
    max_open_positions: int = 3
    daily_profit_lock_pct: float | None = None


@dataclass
class RiskEvaluation:
    """Result of a risk check."""
    decision: RiskDecision
    reason: str | None = None
    profile_name: str = "default"


class RiskEngine:
    """Risk engine — validates signals against all risk rules.

    Not yet implemented — interface defined for Phase 5.
    """
    pass
