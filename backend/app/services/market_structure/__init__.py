"""Market Structure Engine — detect swing points and structure shifts.

Detects:
    - Swing highs / swing lows
    - Higher highs / higher lows (bullish structure)
    - Lower highs / lower lows (bearish structure)
    - Break of Structure (BOS)
    - Change of Character (CHoCH)
    - Market Structure Shift (MSS)

All definitions are mathematical/programmatic, not visual.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class StructureEventType(str, Enum):
    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"
    HIGHER_HIGH = "higher_high"
    HIGHER_LOW = "higher_low"
    LOWER_HIGH = "lower_high"
    LOWER_LOW = "lower_low"
    BOS = "bos"              # Break of Structure
    CHOCH = "choch"          # Change of Character
    MSS = "mss"              # Market Structure Shift


@dataclass
class StructureEvent:
    instrument: str
    timeframe: str
    timestamp: datetime
    event_type: StructureEventType
    price_level: float
    direction: str | None   # "bullish" | "bearish" | None


class MarketStructureEngine(ABC):
    """Abstract interface for market structure detection."""

    @abstractmethod
    def detect_swings(self, bars: list) -> list[StructureEvent]:
        """Detect swing highs and lows from OHLCV bars."""
        ...

    @abstractmethod
    def detect_structure_breaks(self, bars: list, swings: list) -> list[StructureEvent]:
        """Detect BOS, CHoCH, and MSS events."""
        ...
