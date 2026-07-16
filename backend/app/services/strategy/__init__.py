"""Strategy Engine — compose conditions into trade setups.

Modular: conditions are composable. Setup = combination of conditions.
Each strategy version is tracked for backtesting and journaling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class SetupType(str, Enum):
    FVG_RETRACEMENT = "fvg_retracement"
    ORDER_BLOCK = "order_block"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    STRUCTURE_SHIFT = "structure_shift"


@dataclass
class Signal:
    """A validated trade signal from the strategy engine."""
    id: str
    strategy_version: str
    instrument: str
    direction: Direction
    setup_type: SetupType
    entry_price: float
    stop_loss: float
    take_profit: float
    confluence_score: float
    timeframe_context: str
    bias: str | None
    triggering_conditions: dict = field(default_factory=dict)
    generated_at: datetime | None = None
    expires_at: datetime | None = None


class SetupCondition(ABC):
    """A single condition that can be part of a setup."""

    @abstractmethod
    def evaluate(self, context: dict) -> bool:
        """Evaluate whether this condition is met."""
        ...


class StrategyEngine(ABC):
    """Abstract interface for the strategy/setup engine."""

    @abstractmethod
    def generate_signals(self, context: dict) -> list[Signal]:
        """Generate trade signals from the current market context."""
        ...
