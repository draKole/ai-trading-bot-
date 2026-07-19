"""SMT Divergence Detection Engine.

Smart Money Technique (SMT) Divergence occurs when two correlated instruments
diverge at key market structure swing points:

    Bullish SMT: Instrument A makes a Lower Low, but instrument B does NOT.
        → Smart money is accumulating on B; price likely to reverse UP.

    Bearish SMT: Instrument A makes a Higher High, but instrument B does NOT.
        → Smart money is distributing on B; price likely to reverse DOWN.

Detection is based on completed Market Structure swing points (Phase 1B)
compared across instrument pairs within timestamp tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SMTDirection(str, Enum):
    BULLISH = "bullish"   # Lower Low divergence → price going UP
    BEARISH = "bearish"   # Higher High divergence → price going DOWN


class SMTMatchingMethod(str, Enum):
    NEAREST_TIME = "nearest_time"  # Match closest swing in time
    NEAREST_VALUE = "nearest_value"  # Match closest swing in price proximity


@dataclass
class SMTConfig:
    """Configuration for SMT Divergence detection.

    Attributes:
        pairs: List of instrument pair dicts with keys: primary, secondary.
            Example: [{"primary": "ES", "secondary": "NQ"}]
        timestamp_tolerance_seconds: Max seconds between matching swings.
            Default: 300 (5 minutes).
        matching_method: How to match corresponding swings.
            Default: "nearest_time".
        comparison_window_bars: Max bars window for finding matching swings.
            Default: 10.
        require_prior_swings: If True, require both instruments to have
            prior swings for HH/LL comparison. Default: True.
        min_divergence_pct: Minimum % difference between swings to qualify.
            Default: 0.05 (0.05% of price).
        enabled_timeframes: Timeframes to detect on. Empty = all.
            Default: ["5m", "15m", "1h"].
    """
    pairs: list[dict] = field(default_factory=list)
    timestamp_tolerance_seconds: float = 300.0
    matching_method: str = "nearest_time"
    comparison_window_bars: int = 10
    require_prior_swings: bool = True
    min_divergence_pct: float = 0.05
    enabled_timeframes: list[str] = field(default_factory=lambda: ["5m", "15m", "1h"])

    def to_dict(self) -> dict:
        return {
            "pairs": self.pairs,
            "timestamp_tolerance_seconds": self.timestamp_tolerance_seconds,
            "matching_method": self.matching_method,
            "comparison_window_bars": self.comparison_window_bars,
            "require_prior_swings": self.require_prior_swings,
            "min_divergence_pct": self.min_divergence_pct,
            "enabled_timeframes": self.enabled_timeframes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SMTConfig:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SMTEvent:
    """A detected SMT Divergence event."""

    # Identification
    primary_instrument: str
    secondary_instrument: str
    timeframe: str
    direction: str  # "bullish" or "bearish"

    # Primary instrument swing
    primary_swing_type: str  # "swing_high" or "swing_low"
    primary_swing_price: float
    primary_swing_bar_index: int
    primary_swing_timestamp: datetime

    # Secondary instrument swing
    secondary_swing_type: str
    secondary_swing_price: float
    secondary_swing_bar_index: int
    secondary_swing_timestamp: datetime

    # Divergence details
    divergence_pct: float = 0.0
    timestamp_delta_seconds: float = 0.0

    # Optional prior prices for HH/LL comparison
    primary_prior_swing_price: float | None = None
    secondary_prior_swing_price: float | None = None

    # Optional MS event references
    primary_ms_event_id: int | None = None
    secondary_ms_event_id: int | None = None

    # Detection metadata
    detection_timestamp: datetime | None = None
    detection_bar_index: int = 0

    # Related entities
    related_liquidity_ids: list[int] = field(default_factory=list)
    related_fvg_ids: list[int] = field(default_factory=list)
    related_ob_ids: list[int] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"<SMT {self.direction} {self.primary_instrument}/{self.secondary_instrument} "
            f"{self.timeframe} div={self.divergence_pct:.2f}%>"
        )


# ─── Detection ───────────────────────────────────────────────

def detect_smt_divergence(
    primary_swings: list[dict],
    secondary_swings: list[dict],
    primary_instrument: str,
    secondary_instrument: str,
    timeframe: str,
    primary_bars: list | None = None,
    secondary_bars: list | None = None,
    config: SMTConfig | None = None,
) -> list[SMTEvent]:
    """Detect SMT divergence between two instruments' swing points.

    For each swing on the primary instrument, find the nearest matching swing
    on the secondary instrument within timestamp tolerance. Compare whether
    both made new extremes (HH/LL) or only one did.

    Args:
        primary_swings: List of swing dicts for primary instrument.
            Each dict: {swing_type, price, bar_index, timestamp, prior_price, ms_event_id}.
        secondary_swings: Same for secondary instrument.
        primary_instrument, secondary_instrument: Instrument symbols.
        timeframe: Timeframe string.
        config: Detection configuration.

    Returns:
        List of SMTEvent objects.
    """
    if config is None:
        config = SMTConfig()

    if config.enabled_timeframes and timeframe not in config.enabled_timeframes:
        return []

    tol_seconds = config.timestamp_tolerance_seconds
    events: list[SMTEvent] = []
    seen_keys: set[tuple] = set()

    # Build search index for secondary swings by time
    sec_by_type: dict[str, list[dict]] = {"swing_high": [], "swing_low": []}
    for s in secondary_swings:
        st = s.get("swing_type", s.get("event_type", "")).lower()
        if st in ("high", "swing_high", "hh", "lh"):
            sec_by_type["swing_high"].append(s)
        elif st in ("low", "swing_low", "ll", "hl"):
            sec_by_type["swing_low"].append(s)

    for p_swing in primary_swings:
        # Determine swing type from primary
        p_type_raw = p_swing.get("swing_type", p_swing.get("event_type", "")).lower()
        if p_type_raw in ("high", "swing_high", "hh", "lh"):
            p_type = "swing_high"
        elif p_type_raw in ("low", "swing_low", "ll", "hl"):
            p_type = "swing_low"
        else:
            continue

        p_price = _get_price(p_swing)
        p_ts = _get_timestamp(p_swing)
        p_bar = _get_bar_index(p_swing)
        p_id = _get_id(p_swing)
        p_prior = _get_prior_price(p_swing)

        if p_price is None or p_ts is None:
            continue

        # Find nearest secondary swing of same type
        candidates = sec_by_type.get(p_type, [])
        if not candidates:
            continue

        nearest = _find_nearest_swing(p_ts, candidates, config)
        if nearest is None:
            continue

        s_price = _get_price(nearest)
        s_ts = _get_timestamp(nearest)
        s_bar = _get_bar_index(nearest)
        s_id = _get_id(nearest)
        s_prior = _get_prior_price(nearest)

        if s_price is None or s_ts is None:
            continue

        ts_delta = abs((p_ts - s_ts).total_seconds())
        if ts_delta > tol_seconds:
            continue

        # Determine HH/LL vs LH/HL
        if p_prior is not None and s_prior is not None and p_prior > 0 and s_prior > 0:
            p_new_high = p_price > p_prior
            s_new_high = s_price > s_prior
            p_new_low = p_price < p_prior
            s_new_low = s_price < s_prior
        else:
            # No prior swings — compare absolute values if allowed
            if config.require_prior_swings:
                continue
            p_new_high = True
            s_new_high = True
            p_new_low = True
            s_new_low = True

        direction = None
        divergence_pct = 0.0

        if p_type == "swing_high":
            # HH comparison for bearish SMT
            if p_new_high and not s_new_high:
                direction = "bearish"
                # Divergence: how much secondary failed vs its prior
                divergence_pct = ((s_prior - s_price) / s_prior) * 100
            elif s_new_high and not p_new_high:
                direction = "bearish"
                divergence_pct = ((p_prior - p_price) / p_prior) * 100
        else:  # swing_low
            # LL comparison for bullish SMT
            if p_new_low and not s_new_low:
                direction = "bullish"
                # Divergence: how much secondary held above its prior
                divergence_pct = ((s_price - s_prior) / s_prior) * 100
            elif s_new_low and not p_new_low:
                direction = "bullish"
                divergence_pct = ((p_price - p_prior) / p_prior) * 100

        if direction is None:
            continue

        # Minimum divergence filter
        if abs(divergence_pct) < config.min_divergence_pct:
            continue

        # Deduplication
        key = (direction, p_bar, s_bar, timeframe)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        detection_ts = max(p_ts, s_ts) if (p_ts and s_ts) else (
            p_ts if p_ts else s_ts)

        events.append(SMTEvent(
            primary_instrument=primary_instrument,
            secondary_instrument=secondary_instrument,
            timeframe=timeframe,
            direction=direction,
            primary_swing_type=p_type,
            primary_swing_price=p_price,
            primary_swing_bar_index=p_bar or 0,
            primary_swing_timestamp=p_ts,
            primary_prior_swing_price=p_prior,
            primary_ms_event_id=p_id,
            secondary_swing_type=p_type,
            secondary_swing_price=s_price,
            secondary_swing_bar_index=s_bar or 0,
            secondary_swing_timestamp=s_ts,
            secondary_prior_swing_price=s_prior,
            secondary_ms_event_id=s_id,
            divergence_pct=abs(divergence_pct),
            timestamp_delta_seconds=ts_delta,
            detection_timestamp=detection_ts,
            detection_bar_index=max(p_bar or 0, s_bar or 0),
        ))

    return events


def _get_price(swing: dict) -> float | None:
    """Extract price from a swing dict."""
    for key in ("price", "price_level", "value"):
        if key in swing and swing[key] is not None:
            return float(swing[key])
    return None


def _get_timestamp(swing: dict) -> datetime | None:
    """Extract timestamp from a swing dict."""
    for key in ("timestamp", "bar_timestamp", "confirmed_at", "creation_timestamp"):
        val = swing.get(key)
        if val is not None:
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                return datetime.fromisoformat(val)
    return None


def _get_bar_index(swing: dict) -> int | None:
    """Extract bar index from a swing dict."""
    for key in ("bar_index", "index"):
        if key in swing and swing[key] is not None:
            return int(swing[key])
    return None


def _get_id(swing: dict) -> int | None:
    """Extract event ID from a swing dict."""
    for key in ("id", "event_id", "ms_event_id"):
        if key in swing:
            return int(swing[key])
    return None


def _get_prior_price(swing: dict) -> float | None:
    """Extract prior swing price from a swing dict."""
    for key in ("prior_price", "parent_swing_price", "previous_price"):
        if key in swing and swing[key] is not None:
            return float(swing[key])
    return None


def _find_nearest_swing(
    target_ts: datetime,
    candidates: list[dict],
    config: SMTConfig,
) -> dict | None:
    """Find the candidate swing closest in time to target_ts."""
    best = None
    best_delta = float("inf")

    for c in candidates:
        c_ts = _get_timestamp(c)
        if c_ts is None:
            continue
        delta = abs((target_ts - c_ts).total_seconds())
        if delta < best_delta:
            best_delta = delta
            best = c

    return best
