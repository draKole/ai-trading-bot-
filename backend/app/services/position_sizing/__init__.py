"""Position Sizing Engine — calculate contract quantity.

Based on instrument specs (tick size, tick value), entry price,
stop distance, and maximum permitted risk. Never increases size
to hit a profit target.
"""

from dataclasses import dataclass


@dataclass
class InstrumentSpec:
    """Specifications for a futures instrument."""
    symbol: str
    tick_size: float
    tick_value: float          # Dollar value per tick per contract
    multiplier: int
    min_contracts: int = 1
    max_contracts: int = 10


@dataclass
class PositionSize:
    contracts: int
    dollar_risk: float
    stop_distance_ticks: int
    rejected: bool = False
    rejection_reason: str | None = None


class PositionSizer:
    """Calculate position size from entry, stop, and risk parameters.

    Not yet implemented — interface defined for Phase 5.
    """
    pass
