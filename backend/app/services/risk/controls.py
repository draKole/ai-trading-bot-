"""Execution Risk Controls — kill switch, circuit breaker, daily loss limit, max position.

Separate from the advisory Risk Engine (which scores setups).
These are execution-level safety controls enforced in both PAPER and LIVE modes.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ─── Config ────────────────────────────────────────────────

@dataclass
class ExecutionRiskConfig:
    """Configurable risk control parameters. All settable via env vars."""

    # Daily loss limit — auto-flattens when daily realized + unrealized hits this
    daily_loss_limit: float = 1000.0

    # Circuit breaker: activate kill switch after N consecutive losses in M seconds
    circuit_breaker_consecutive_losses: int = 3
    circuit_breaker_window_seconds: int = 300  # 5 minutes

    # Max position size per instrument
    max_position_size: dict[str, int] = field(default_factory=lambda: {
        "ES": 10, "NQ": 5, "MNQ": 10,
    })

    # Whether risk checks are enabled
    kill_switch_enabled: bool = True
    circuit_breaker_enabled: bool = True
    daily_loss_limit_enabled: bool = True
    max_position_enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "daily_loss_limit": self.daily_loss_limit,
            "circuit_breaker_consecutive_losses": self.circuit_breaker_consecutive_losses,
            "circuit_breaker_window_seconds": self.circuit_breaker_window_seconds,
            "max_position_size": dict(self.max_position_size),
            "kill_switch_enabled": self.kill_switch_enabled,
            "circuit_breaker_enabled": self.circuit_breaker_enabled,
            "daily_loss_limit_enabled": self.daily_loss_limit_enabled,
            "max_position_enabled": self.max_position_enabled,
        }

    @classmethod
    def from_env(cls) -> ExecutionRiskConfig:
        """Load config from environment variables with sensible defaults."""
        return cls(
            daily_loss_limit=float(os.environ.get("RISK_DAILY_LOSS_LIMIT", "1000")),
            circuit_breaker_consecutive_losses=int(os.environ.get("RISK_CB_CONSECUTIVE", "3")),
            circuit_breaker_window_seconds=int(os.environ.get("RISK_CB_WINDOW_SECONDS", "300")),
            max_position_size={
                "ES": int(os.environ.get("RISK_MAX_POS_ES", "10")),
                "NQ": int(os.environ.get("RISK_MAX_POS_NQ", "5")),
                "MNQ": int(os.environ.get("RISK_MAX_POS_MNQ", "10")),
            },
        )


# ─── Circuit Breaker Tracker ───────────────────────────────

@dataclass
class _LossRecord:
    """Records a single loss for circuit breaker tracking."""
    timestamp: float = field(default_factory=time.time)
    amount: float = 0.0


class CircuitBreakerTracker:
    """Tracks consecutive losses within a time window for circuit breaker logic."""

    def __init__(self, window_seconds: int = 300, max_consecutive: int = 3):
        self.window_seconds = window_seconds
        self.max_consecutive = max_consecutive
        self._losses: list[_LossRecord] = []

    def record_loss(self, amount: float) -> None:
        """Record a losing trade."""
        self._losses.append(_LossRecord(amount=abs(amount)))
        self._prune()

    def record_win(self) -> None:
        """A win resets the consecutive loss counter."""
        self._losses.clear()

    def is_triggered(self) -> bool:
        """Check if circuit breaker should fire."""
        self._prune()
        if len(self._losses) >= self.max_consecutive:
            total_loss = sum(l.amount for l in self._losses)
            return total_loss > 0
        return False

    @property
    def consecutive_losses(self) -> int:
        self._prune()
        return len(self._losses)

    def _prune(self) -> None:
        """Remove losses outside the time window."""
        cutoff = time.time() - self.window_seconds
        self._losses = [l for l in self._losses if l.timestamp >= cutoff]

    def reset(self) -> None:
        self._losses.clear()


# ─── Daily Loss Tracker ────────────────────────────────────

class DailyLossTracker:
    """Tracks daily realized losses across all positions."""

    def __init__(self, limit: float = 1000.0):
        self.limit = limit
        self._daily_loss: float = 0.0
        self._last_reset_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def record_pnl(self, pnl: float) -> None:
        """Record a P&L event. Negative = loss."""
        self._maybe_reset()
        if pnl < 0:
            self._daily_loss += abs(pnl)

    def is_exceeded(self, additional_unrealized: float = 0.0) -> bool:
        """Check if daily loss limit is exceeded."""
        self._maybe_reset()
        return (self._daily_loss + abs(additional_unrealized)) >= self.limit

    @property
    def current_loss(self) -> float:
        self._maybe_reset()
        return self._daily_loss

    def _maybe_reset(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._daily_loss = 0.0
            self._last_reset_date = today

    def reset(self) -> None:
        self._daily_loss = 0.0


# ─── Execution Risk Controller ─────────────────────────────

class ExecutionRiskController:
    """Execution-level risk controls: kill switch, circuit breaker, daily loss, max position.

    Works with both paper and live trading. The ModeManager kill switch
    (global) is separate — this is the session-level kill switch.
    """

    def __init__(self, config: ExecutionRiskConfig | None = None):
        self.config = config or ExecutionRiskConfig()
        self._killed = False
        self._killed_at: Optional[datetime] = None
        self._circuit_breaker = CircuitBreakerTracker(
            window_seconds=self.config.circuit_breaker_window_seconds,
            max_consecutive=self.config.circuit_breaker_consecutive_losses,
        )
        self._daily_loss = DailyLossTracker(limit=self.config.daily_loss_limit)
        self._positions: dict[str, int] = {}  # instrument -> current quantity

    @property
    def is_killed(self) -> bool:
        return self._killed

    def kill(self) -> dict:
        """Activate kill switch. Irreversible for the session."""
        if self._killed:
            return {"status": "already_killed", "message": "Kill switch was already active"}
        self._killed = True
        self._killed_at = datetime.now(timezone.utc)
        return {
            "status": "killed",
            "message": "Kill switch activated — all trading halted",
            "killed_at": self._killed_at.isoformat(),
        }

    def check_order(
        self, instrument: str, quantity: int, side: str,
    ) -> tuple[bool, str]:
        """Validate an order before execution. Returns (allowed, reason).

        Checks: kill switch, max position size.
        """
        if not self.config.kill_switch_enabled:
            return True, "OK (kill switch disabled)"

        if self._killed:
            return False, "Kill switch active — trading halted"

        if self.config.max_position_enabled:
            max_pos = self.config.max_position_size.get(instrument, 10)
            current_qty = self._positions.get(instrument, 0)
            proposed_qty = current_qty + quantity if side == "buy" else current_qty - quantity

            if abs(proposed_qty) > max_pos:
                return False, (
                    f"Max position size exceeded: {abs(proposed_qty)} > {max_pos} for {instrument}"
                )

        return True, "OK"

    def record_trade(self, pnl: float) -> None:
        """Record a completed trade's P&L for circuit breaker and daily loss tracking."""
        self._daily_loss.record_pnl(pnl)

        if self.config.circuit_breaker_enabled:
            if pnl < 0:
                self._circuit_breaker.record_loss(pnl)
            else:
                self._circuit_breaker.record_win()

            if self._circuit_breaker.is_triggered():
                self.kill()

        if self.config.daily_loss_limit_enabled:
            if self._daily_loss.is_exceeded():
                self.kill()

    def update_position(self, instrument: str, quantity: int, side: str) -> None:
        """Track position for max position calculation."""
        current = self._positions.get(instrument, 0)
        if side == "buy":
            self._positions[instrument] = current + quantity
        else:
            self._positions[instrument] = current - quantity

    def get_status(self) -> dict:
        """Get current risk state as dict."""
        return {
            "killed": self._killed,
            "killed_at": self._killed_at.isoformat() if self._killed_at else None,
            "circuit_breaker": {
                "consecutive_losses": self._circuit_breaker.consecutive_losses,
                "max_consecutive": self.config.circuit_breaker_consecutive_losses,
                "window_seconds": self.config.circuit_breaker_window_seconds,
                "enabled": self.config.circuit_breaker_enabled,
            },
            "daily_loss": {
                "current_loss": round(self._daily_loss.current_loss, 2),
                "limit": self.config.daily_loss_limit,
                "exceeded": self._daily_loss.is_exceeded(),
                "enabled": self.config.daily_loss_limit_enabled,
            },
            "max_position": {
                "current": dict(self._positions),
                "limits": dict(self.config.max_position_size),
                "enabled": self.config.max_position_enabled,
            },
            "kill_switch_enabled": self.config.kill_switch_enabled,
        }
