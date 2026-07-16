"""Liquidity Engine — track and monitor liquidity levels.

Tracks:
    - Previous Day High/Low, Previous Week High/Low
    - Session highs/lows (Asian, London, NY)
    - Equal highs / equal lows
    - Swing liquidity
    - Liquidity sweeps (approach, touch, sweep, reject, close-through)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class LiquidityLevelType(str, Enum):
    PDH = "pdh"
    PDL = "pdl"
    PWH = "pwh"
    PWL = "pwl"
    ASIAN_HIGH = "asian_high"
    ASIAN_LOW = "asian_low"
    LONDON_HIGH = "london_high"
    LONDON_LOW = "london_low"
    NY_HIGH = "ny_high"
    NY_LOW = "ny_low"
    EQUAL_HIGHS = "equal_highs"
    EQUAL_LOWS = "equal_lows"
    SWING_LIQUIDITY = "swing_liquidity"


class SweepResult(str, Enum):
    APPROACHED = "approached"
    TOUCHED = "touched"
    SWEPT = "swept"
    REJECTED = "rejected"
    CLOSED_THROUGH = "closed_through"


@dataclass
class LiquidityLevel:
    instrument: str
    timeframe: str
    level_type: LiquidityLevelType
    price: float
    source_bar_time: datetime
    swept_at: datetime | None = None
    is_active: bool = True


class LiquidityEngine(ABC):
    """Abstract interface for liquidity detection and tracking."""

    @abstractmethod
    def detect_levels(self, bars: list) -> list[LiquidityLevel]:
        """Detect all liquidity levels from price data."""
        ...

    @abstractmethod
    def evaluate_sweep(self, level: LiquidityLevel, current_bar) -> SweepResult:
        """Determine how price interacted with a liquidity level."""
        ...
