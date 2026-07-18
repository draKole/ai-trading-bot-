"""FVG Detection Engine — identifies Fair Value Gaps from OHLCV bars.

A Fair Value Gap (FVG) is a 3-candle price imbalance pattern:

    Bullish FVG: low[2] > high[0]
        Gap exists between high[0] (lower bound) and low[2] (upper bound).
        Indicates price moved up too fast — gap may fill downward.

    Bearish FVG: high[2] < low[0]
        Gap exists between low[0] (upper bound) and high[2] (lower bound).
        Indicates price moved down too fast — gap may fill upward.

All definitions are deterministic and mathematical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class FVGDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class FVGStatus(str, Enum):
    ACTIVE = "active"
    PARTIALLY_FILLED = "partially_filled"
    MITIGATED = "mitigated"
    INVALIDATED = "invalidated"


@dataclass
class FVGConfig:
    """Configuration for FVG detection and lifecycle.

    Attributes:
        min_gap_size: Minimum absolute gap size (in price units). Default: 0.0.
        min_gap_size_pct: Minimum gap as % of midpoint. Default: 0.01 (0.01%).
        fill_tolerance_pct: Tolerance for "fully mitigated" — if fill % >=
            (100 - fill_tolerance_pct), gap is mitigated. Default: 1.0.
        use_close_for_fill: If True, uses bar close for fill determination.
            If False, uses bar high/low (wicks). Default: False.
        invalidation_pct: If price moves beyond the gap by this % in the
            opposite direction, the FVG is invalidated. Default: 0.5.
        max_age_bars: Maximum bars an FVG can exist before auto-invalidation.
            0 = never. Default: 0.
        enabled_timeframes: List of timeframes to detect on. Empty = all.
    """
    min_gap_size: float = 0.0
    min_gap_size_pct: float = 0.01
    fill_tolerance_pct: float = 1.0
    use_close_for_fill: bool = False
    invalidation_pct: float = 0.5
    max_age_bars: int = 0
    enabled_timeframes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "min_gap_size": self.min_gap_size,
            "min_gap_size_pct": self.min_gap_size_pct,
            "fill_tolerance_pct": self.fill_tolerance_pct,
            "use_close_for_fill": self.use_close_for_fill,
            "invalidation_pct": self.invalidation_pct,
            "max_age_bars": self.max_age_bars,
            "enabled_timeframes": self.enabled_timeframes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FVGConfig:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class FVG:
    """A detected Fair Value Gap.

    Bounds:
        Bullish: upper_bound = low[2], lower_bound = high[0]
        Bearish:  upper_bound = low[0], lower_bound = high[2]

    In both cases, upper_bound > lower_bound.
    """
    instrument: str
    timeframe: str
    direction: str  # "bullish" or "bearish"
    upper_bound: float
    lower_bound: float
    creation_bar_index: int
    creation_timestamp: datetime

    # Derived
    midpoint: float = 0.0
    gap_size: float = 0.0
    gap_size_pct: float = 0.0

    # Lifecycle
    status: str = "active"
    first_touch_timestamp: datetime | None = None
    first_touch_bar_index: int | None = None
    mitigation_timestamp: datetime | None = None
    mitigation_bar_index: int | None = None
    invalidation_timestamp: datetime | None = None
    invalidation_bar_index: int | None = None
    fill_percentage: float = 0.0

    # Metadata
    candle_1_high: float = 0.0
    candle_1_low: float = 0.0
    candle_2_high: float = 0.0
    candle_2_low: float = 0.0
    candle_3_high: float = 0.0
    candle_3_low: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.midpoint == 0.0:
            self.midpoint = (self.upper_bound + self.lower_bound) / 2
        if self.gap_size == 0.0:
            self.gap_size = self.upper_bound - self.lower_bound
        if self.gap_size_pct == 0.0 and self.midpoint > 0:
            self.gap_size_pct = (self.gap_size / self.midpoint) * 100

    def __repr__(self) -> str:
        return (
            f"<FVG {self.direction} [{self.lower_bound:.2f}–{self.upper_bound:.2f}] "
            f"{self.status} fill={self.fill_percentage:.1f}%>"
        )


# ─── Detection ───────────────────────────────────────────────

def detect_fvgs(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    timestamps: list[datetime],
    instrument: str,
    timeframe: str,
    config: FVGConfig | None = None,
) -> list[FVG]:
    """Detect FVGs from OHLCV data using 3-candle patterns.

    Args:
        highs, lows, closes: Price arrays (same length).
        timestamps: Bar timestamps.
        instrument: Instrument symbol.
        timeframe: Timeframe string.
        config: Detection configuration.

    Returns:
        List of detected FVG objects (post-creation only; lifecycle not applied).
    """
    if config is None:
        config = FVGConfig()

    # Check timeframe filter
    if config.enabled_timeframes and timeframe not in config.enabled_timeframes:
        return []

    n = len(highs)
    if n < 3:
        return []

    fvgs: list[FVG] = []

    for i in range(2, n):
        h0, l0 = highs[i - 2], lows[i - 2]
        h2, l2 = highs[i], lows[i]

        # ── Bullish FVG: low of candle 3 > high of candle 1 ──
        if l2 > h0:
            upper = l2
            lower = h0
            gap_size = upper - lower
            midpoint = (upper + lower) / 2
            gap_pct = (gap_size / midpoint) * 100 if midpoint > 0 else 0

            if _passes_filters(gap_size, gap_pct, config):
                fvgs.append(FVG(
                    instrument=instrument,
                    timeframe=timeframe,
                    direction="bullish",
                    upper_bound=upper,
                    lower_bound=lower,
                    creation_bar_index=i,
                    creation_timestamp=timestamps[i],
                    midpoint=midpoint,
                    gap_size=gap_size,
                    gap_size_pct=gap_pct,
                    candle_1_high=h0, candle_1_low=l0,
                    candle_2_high=highs[i - 1], candle_2_low=lows[i - 1],
                    candle_3_high=h2, candle_3_low=l2,
                ))

        # ── Bearish FVG: high of candle 3 < low of candle 1 ──
        elif h2 < l0:
            upper = l0
            lower = h2
            gap_size = upper - lower
            midpoint = (upper + lower) / 2
            gap_pct = (gap_size / midpoint) * 100 if midpoint > 0 else 0

            if _passes_filters(gap_size, gap_pct, config):
                fvgs.append(FVG(
                    instrument=instrument,
                    timeframe=timeframe,
                    direction="bearish",
                    upper_bound=upper,
                    lower_bound=lower,
                    creation_bar_index=i,
                    creation_timestamp=timestamps[i],
                    midpoint=midpoint,
                    gap_size=gap_size,
                    gap_size_pct=gap_pct,
                    candle_1_high=h0, candle_1_low=l0,
                    candle_2_high=highs[i - 1], candle_2_low=lows[i - 1],
                    candle_3_high=h2, candle_3_low=l2,
                ))

    return fvgs


def _passes_filters(gap_size: float, gap_pct: float, config: FVGConfig) -> bool:
    """Check if a gap passes minimum size filters."""
    if gap_size <= 0:
        return False
    if config.min_gap_size > 0 and gap_size < config.min_gap_size:
        return False
    if config.min_gap_size_pct > 0 and gap_pct < config.min_gap_size_pct:
        return False
    return True


# ─── Lifecycle Management ────────────────────────────────────

@dataclass
class FVGLifecycleEvent:
    """A lifecycle state change for an FVG."""
    fvg_id: int | None  # DB ID, None for in-memory
    event_type: str  # "created", "first_touch", "partial_fill", "mitigated", "invalidated"
    bar_index: int
    timestamp: datetime
    fill_percentage: float
    metadata: dict = field(default_factory=dict)


def apply_lifecycle(
    fvgs: list[FVG],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    timestamps: list[datetime],
    config: FVGConfig | None = None,
) -> tuple[list[FVG], list[FVGLifecycleEvent]]:
    """Apply lifecycle tracking to detected FVGs.

    For each FVG, scan forward from creation to determine:
    - If/when it gets first touched
    - Fill percentage over time
    - When it becomes fully mitigated
    - When/if it gets invalidated

    Returns updated FVGs and lifecycle events.
    """
    if config is None:
        config = FVGConfig()

    n = len(highs)
    events: list[FVGLifecycleEvent] = []

    for fvg in fvgs:
        start_idx = fvg.creation_bar_index + 1
        gap_range = fvg.upper_bound - fvg.lower_bound

        # Always emit creation event first
        events.append(FVGLifecycleEvent(
            fvg_id=None, event_type="created",
            bar_index=fvg.creation_bar_index,
            timestamp=fvg.creation_timestamp,
            fill_percentage=0.0,
        ))

        if start_idx >= n or gap_range <= 0:
            continue

        use_close = config.use_close_for_fill
        fill_tol = config.fill_tolerance_pct / 100.0
        inval_pct = config.invalidation_pct / 100.0
        max_age = config.max_age_bars
        max_fill_seen = 0.0

        for i in range(start_idx, n):
            # Check max age
            if max_age > 0 and (i - fvg.creation_bar_index) > max_age:
                fvg.status = FVGStatus.INVALIDATED.value
                fvg.invalidation_bar_index = i
                fvg.invalidation_timestamp = timestamps[i]
                events.append(FVGLifecycleEvent(
                    fvg_id=None, event_type="invalidated",
                    bar_index=i, timestamp=timestamps[i],
                    fill_percentage=fvg.fill_percentage,
                    metadata={"reason": "max_age_exceeded"},
                ))
                break

            # Determine how much of the gap has been traded through
            if fvg.direction == "bullish":
                # Bullish FVG: upper=low[2], lower=high[0]
                # Price coming DOWN fills the gap
                # Fill from upper bound downward
                price_level = closes[i] if use_close else lows[i]
                if price_level <= fvg.lower_bound:
                    # Fully through the gap
                    fill = 100.0
                elif price_level >= fvg.upper_bound:
                    fill = 0.0
                else:
                    fill = ((fvg.upper_bound - price_level) / gap_range) * 100
            else:
                # Bearish FVG: upper=low[0], lower=high[2]
                # Price coming UP fills the gap
                # Fill from lower bound upward
                price_level = closes[i] if use_close else highs[i]
                if price_level >= fvg.upper_bound:
                    fill = 100.0
                elif price_level <= fvg.lower_bound:
                    fill = 0.0
                else:
                    fill = ((price_level - fvg.lower_bound) / gap_range) * 100

            fill = max(0.0, min(100.0, fill))
            fvg.fill_percentage = max(fvg.fill_percentage, fill)

            # First touch
            if fill > 0 and fvg.first_touch_timestamp is None:
                fvg.first_touch_timestamp = timestamps[i]
                fvg.first_touch_bar_index = i
                fvg.status = FVGStatus.PARTIALLY_FILLED.value
                events.append(FVGLifecycleEvent(
                    fvg_id=None, event_type="first_touch",
                    bar_index=i, timestamp=timestamps[i],
                    fill_percentage=fill,
                ))

            # Partial fill
            if fill > 0 and fill < 100 - fill_tol * 100:
                if fvg.status == FVGStatus.ACTIVE.value:
                    fvg.status = FVGStatus.PARTIALLY_FILLED.value
                if fill > max_fill_seen + 10:  # Emit on significant fill changes
                    max_fill_seen = fill
                    events.append(FVGLifecycleEvent(
                        fvg_id=None, event_type="partial_fill",
                        bar_index=i, timestamp=timestamps[i],
                        fill_percentage=fill,
                    ))

            # Fully mitigated
            if fill >= 100 - fill_tol * 100:
                fvg.status = FVGStatus.MITIGATED.value
                fvg.mitigation_timestamp = timestamps[i]
                fvg.mitigation_bar_index = i
                fvg.fill_percentage = 100.0
                events.append(FVGLifecycleEvent(
                    fvg_id=None, event_type="mitigated",
                    bar_index=i, timestamp=timestamps[i],
                    fill_percentage=100.0,
                ))
                break

            # Invalidation: price goes significantly beyond the gap
            if fvg.direction == "bullish":
                # Bullish FVG invalidated if price rallies well above upper bound
                if closes[i] > fvg.upper_bound * (1 + inval_pct):
                    fvg.status = FVGStatus.INVALIDATED.value
                    fvg.invalidation_timestamp = timestamps[i]
                    fvg.invalidation_bar_index = i
                    events.append(FVGLifecycleEvent(
                        fvg_id=None, event_type="invalidated",
                        bar_index=i, timestamp=timestamps[i],
                        fill_percentage=fvg.fill_percentage,
                        metadata={"reason": "price_extended_above"},
                    ))
                    break
            else:
                if closes[i] < fvg.lower_bound * (1 - inval_pct):
                    fvg.status = FVGStatus.INVALIDATED.value
                    fvg.invalidation_timestamp = timestamps[i]
                    fvg.invalidation_bar_index = i
                    events.append(FVGLifecycleEvent(
                        fvg_id=None, event_type="invalidated",
                        bar_index=i, timestamp=timestamps[i],
                        fill_percentage=fvg.fill_percentage,
                        metadata={"reason": "price_extended_below"},
                    ))
                    break

    # Sort events by bar_index
    events.sort(key=lambda e: (e.bar_index, _event_priority(e.event_type)))
    return fvgs, events


def _event_priority(event_type: str) -> int:
    return {"created": 0, "first_touch": 1, "partial_fill": 2, "mitigated": 3, "invalidated": 4}.get(event_type, 5)
