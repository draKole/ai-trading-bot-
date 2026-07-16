"""Fair Value Gap Engine — detect, track, and score FVGs.

Detects bullish and bearish FVGs. Tracks fill status, mitigation,
and multi-timeframe overlap for confluence scoring.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class FVGDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class FairValueGap:
    instrument: str
    timeframe: str
    direction: FVGDirection
    creation_timestamp: datetime
    upper_boundary: float
    lower_boundary: float
    midpoint: float
    size_pct: float
    has_been_entered: bool = False
    fill_pct: float = 0.0
    is_mitigated: bool = False
    is_active: bool = True


class FVGEngine(ABC):
    """Abstract interface for FVG detection and tracking."""

    @abstractmethod
    def detect(self, bars: list) -> list[FairValueGap]:
        """Detect FVGs from OHLCV bars."""
        ...

    @abstractmethod
    def update_fill_status(self, fvg: FairValueGap, current_bar) -> FairValueGap:
        """Update an FVG's fill percentage and mitigation status."""
        ...

    @abstractmethod
    def find_mtf_overlaps(self, fvgs: list) -> dict:
        """Identify multi-timeframe FVG overlaps and return confluence data."""
        ...
