"""Order Block Engine — detect, track, and validate order blocks.

Configurable definitions for bullish/bearish order blocks,
mitigation, and invalidation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OBDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class OrderBlock:
    instrument: str
    timeframe: str
    direction: OBDirection
    upper_boundary: float
    lower_boundary: float
    creation_bar_time: datetime
    mitigated_at: datetime | None = None
    is_invalidated: bool = False
    is_active: bool = True


class OrderBlockEngine(ABC):
    """Abstract interface for order block detection and tracking."""

    @abstractmethod
    def detect(self, bars: list) -> list[OrderBlock]:
        """Detect order blocks from OHLCV bars."""
        ...

    @abstractmethod
    def check_mitigation(self, ob: OrderBlock, current_bar) -> bool:
        """Check if an order block has been mitigated."""
        ...

    @abstractmethod
    def check_invalidation(self, ob: OrderBlock, current_bar) -> bool:
        """Check if an order block has been invalidated."""
        ...
