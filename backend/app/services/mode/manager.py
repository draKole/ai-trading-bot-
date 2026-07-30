"""Mode Manager — config-driven PAPER/LIVE switching.

Reads TRADING_MODE from environment (default: "paper"). 
Allows runtime toggle with explicit confirmation ("confirm=true").

Paper and live share identical API surface but are fully isolated:
- Paper orders never touch the live broker
- Live orders require broker connectivity
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


VALID_MODES = ("paper", "live")
DEFAULT_MODE = "paper"


@dataclass
class ModeState:
    """Current trading mode state."""
    mode: str = DEFAULT_MODE
    configured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_switched_at: Optional[datetime] = None
    switched_by: str = "env"
    confirm_required: bool = True

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    @property
    def is_paper(self) -> bool:
        return self.mode == "paper"


class ModeManager:
    """Manages trading mode (PAPER/LIVE) throughout the application.

    Singleton-like — one instance per process, used by all API routes.
    Paper is the safe default. LIVE must be explicitly enabled.
    """

    def __init__(self) -> None:
        initial_mode = os.environ.get("TRADING_MODE", DEFAULT_MODE).lower().strip()
        if initial_mode not in VALID_MODES:
            initial_mode = DEFAULT_MODE

        self._state = ModeState(
            mode=initial_mode,
            switched_by="env",
        )
        self._killed = False

    @property
    def mode(self) -> str:
        return self._state.mode

    @property
    def is_live(self) -> bool:
        return self._state.is_live

    @property
    def is_paper(self) -> bool:
        return self._state.is_paper

    @property
    def is_killed(self) -> bool:
        return self._killed

    @property
    def state(self) -> dict:
        return {
            "mode": self._state.mode,
            "is_live": self._state.is_live,
            "is_paper": self._state.is_paper,
            "configured_at": self._state.configured_at.isoformat(),
            "last_switched_at": (
                self._state.last_switched_at.isoformat()
                if self._state.last_switched_at else None
            ),
            "killed": self._killed,
        }

    def switch_mode(self, target_mode: str, confirm: bool = False) -> dict:
        """Switch trading mode. Requires explicit confirmation for safety.

        Args:
            target_mode: "paper" or "live"
            confirm: Must be True to execute the switch

        Returns:
            Dict with status and message

        Raises:
            ValueError: if mode is invalid or confirm is False
        """
        target = target_mode.lower().strip()
        if target not in VALID_MODES:
            raise ValueError(f"Invalid mode: {target_mode}. Valid: {VALID_MODES}")

        if target == self._state.mode:
            return {"status": "unchanged", "mode": target, "message": f"Already in {target} mode"}

        if not confirm:
            return {
                "status": "confirmation_required",
                "current": self._state.mode,
                "requested": target,
                "message": f"Switch to {target.upper()} requires confirm=true",
            }

        if self._killed:
            return {"status": "rejected", "message": "Kill switch is active — cannot change mode"}

        old_mode = self._state.mode
        self._state.mode = target
        self._state.last_switched_at = datetime.now(timezone.utc)
        self._state.switched_by = "api"

        return {
            "status": "switched",
            "previous": old_mode,
            "current": target,
            "message": f"Switched from {old_mode.upper()} to {target.upper()}",
            "switched_at": self._state.last_switched_at.isoformat(),
        }

    def kill(self) -> dict:
        """Activate irreversible kill switch. All trading halted."""
        if self._killed:
            return {"status": "already_killed", "message": "Kill switch was already active"}
        self._killed = True
        return {
            "status": "killed",
            "mode": self._state.mode,
            "message": "KILL SWITCH ACTIVATED — all trading halted. Irreversible for this session.",
        }

    def check_can_trade(self) -> tuple[bool, str]:
        """Check if trading is currently allowed. Returns (allowed, reason)."""
        if self._killed:
            return False, "Kill switch active — trading halted"
        return True, "OK"


# Global singleton
_mode_manager: ModeManager | None = None


def get_mode_manager() -> ModeManager:
    """Get the global ModeManager singleton."""
    global _mode_manager
    if _mode_manager is None:
        _mode_manager = ModeManager()
    return _mode_manager
