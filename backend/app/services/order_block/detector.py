"""Order Block Detection Engine.

An Order Block is a candle (or small structure) that precedes a strong
directional move confirmed by a Market Structure break (BOS/CHoCH).

Definitions:
    Bullish OB: The last bearish candle before a bullish BOS/CHoCH.
        - Candle must have close < open (down candle).
        - Bounds: high → open (sell-side liquidity absorbed on breakout).

    Bearish OB: The last bullish candle before a bearish BOS/CHoCH.
        - Candle must have close > open (up candle).
        - Bounds: open → low (buy-side liquidity absorbed on breakdown).

All definitions are deterministic and traceable to originating Market Structure events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OBDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class OBStatus(str, Enum):
    ACTIVE = "active"
    TOUCHED = "touched"
    PARTIALLY_MITIGATED = "partially_mitigated"
    MITIGATED = "mitigated"
    INVALIDATED = "invalidated"


@dataclass
class OBConfig:
    """Configuration for Order Block detection and lifecycle.

    Attributes:
        lookback_bars: Max bars to look back from BOS/CHoCH for OB candle.
            Default: 5.
        require_bos_choch: If True, only create OBs when a BOS/CHoCH is present.
            If False, also detect standalone OBs from strong moves. Default: True.
        use_open_close_bounds: If True, bounds = [min(o,c), max(o,c)].
            If False, bullish: [open, high], bearish: [low, open].
            Default: False (use high/open and open/low).
        min_body_size_pct: Minimum candle body as % of total range (high-low).
            Default: 0.0.
        max_block_size_pct: Maximum block size as % of price (filters outliers).
            Default: 5.0.
        mitigation_method: "close" = close must cross OB; "wick" = any part.
            Default: "close".
        mitigation_threshold_pct: % of OB range that must be crossed for mitigation.
            Default: 100.0 (fully crossed).
        invalidation_pct: Price extension beyond OB that triggers invalidation.
            Default: 0.5.
        expiration_bars: Max bars before auto-invalidation. 0 = never.
            Default: 0.
        enabled_timeframes: Timeframes to detect on. Empty = all.
    """
    lookback_bars: int = 5
    require_bos_choch: bool = True
    use_open_close_bounds: bool = False
    min_body_size_pct: float = 0.0
    max_block_size_pct: float = 5.0
    mitigation_method: str = "close"
    mitigation_threshold_pct: float = 100.0
    invalidation_pct: float = 0.5
    expiration_bars: int = 0
    enabled_timeframes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "lookback_bars": self.lookback_bars,
            "require_bos_choch": self.require_bos_choch,
            "use_open_close_bounds": self.use_open_close_bounds,
            "min_body_size_pct": self.min_body_size_pct,
            "max_block_size_pct": self.max_block_size_pct,
            "mitigation_method": self.mitigation_method,
            "mitigation_threshold_pct": self.mitigation_threshold_pct,
            "invalidation_pct": self.invalidation_pct,
            "expiration_bars": self.expiration_bars,
            "enabled_timeframes": self.enabled_timeframes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> OBConfig:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class OrderBlock:
    """A detected Order Block traceable to a Market Structure event."""

    instrument: str
    timeframe: str
    direction: str  # "bullish" or "bearish"
    upper_bound: float
    lower_bound: float
    origin_candle_index: int       # The OB candle index
    creation_bar_index: int        # The bar where BOS/CHoCH confirmed it
    creation_timestamp: datetime

    # Derived
    midpoint: float = 0.0
    block_size: float = 0.0
    block_size_pct: float = 0.0

    # Lifecycle
    status: str = "active"
    first_touch_timestamp: datetime | None = None
    first_touch_bar_index: int | None = None
    mitigation_timestamp: datetime | None = None
    mitigation_bar_index: int | None = None
    invalidation_timestamp: datetime | None = None
    invalidation_bar_index: int | None = None
    mitigation_percentage: float = 0.0

    # Related entities
    related_ms_event_id: int | None = None       # Market Structure event ID
    related_liquidity_ids: list[int] = field(default_factory=list)
    related_fvg_ids: list[int] = field(default_factory=list)

    # Origin candle data
    origin_open: float = 0.0
    origin_high: float = 0.0
    origin_low: float = 0.0
    origin_close: float = 0.0
    origin_volume: float = 0.0

    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.midpoint == 0.0:
            self.midpoint = (self.upper_bound + self.lower_bound) / 2
        if self.block_size == 0.0:
            self.block_size = self.upper_bound - self.lower_bound
        if self.block_size_pct == 0.0 and self.midpoint > 0:
            self.block_size_pct = (self.block_size / self.midpoint) * 100

    def __repr__(self) -> str:
        return (
            f"<OB {self.direction} [{self.lower_bound:.2f}–{self.upper_bound:.2f}] "
            f"{self.status} mit={self.mitigation_percentage:.1f}%>"
        )


# ─── Detection ───────────────────────────────────────────────

def detect_order_blocks(
    highs: list[float],
    lows: list[float],
    opens: list[float],
    closes: list[float],
    volumes: list[float],
    timestamps: list[datetime],
    ms_events: list[dict],   # Market Structure events from Phase 1B
    instrument: str,
    timeframe: str,
    config: OBConfig | None = None,
) -> list[OrderBlock]:
    """Detect Order Blocks from OHLCV data and Market Structure events.

    For each bullish BOS/CHoCH event:
        Look back from the event bar to find the last bearish candle (close < open).
        That candle becomes a Bullish OB.

    For each bearish BOS/CHoCH event:
        Look back from the event bar to find the last bullish candle (close > open).
        That candle becomes a Bearish OB.

    Args:
        highs, lows, opens, closes, volumes: Price arrays.
        timestamps: Bar timestamps.
        ms_events: List of Market Structure event dicts with keys:
            bar_index, event_type (BOS/CHoCH), direction (bullish/bearish), id.
        instrument: Instrument symbol.
        timeframe: Timeframe string.
        config: Detection configuration.

    Returns:
        List of detected OrderBlock objects.
    """
    if config is None:
        config = OBConfig()

    if config.enabled_timeframes and timeframe not in config.enabled_timeframes:
        return []

    n = len(highs)
    if n < 2:
        return []

    # Filter MS events to BOS/CHoCH only
    qualifying_events = [
        e for e in ms_events
        if e.get("event_type", "").upper() in ("BOS", "CHOCH", "MSS")
    ]

    if config.require_bos_choch and not qualifying_events:
        return []

    obs: list[OrderBlock] = []
    seen_keys: set[tuple] = set()  # (direction, origin_candle_index) for dedup

    for ms_evt in qualifying_events:
        evt_bar = ms_evt.get("bar_index", ms_evt.get("creation_bar_index", -1))
        evt_direction = ms_evt.get("direction", "").lower()
        evt_type = ms_evt.get("event_type", "").upper()
        evt_id = ms_evt.get("id")

        if evt_bar < 1 or evt_bar >= n:
            continue

        lookback = min(config.lookback_bars, evt_bar)
        ob_found = False

        for back in range(1, lookback + 1):
            cand_idx = evt_bar - back
            if cand_idx < 0:
                break

            o = opens[cand_idx]
            c = closes[cand_idx]
            h = highs[cand_idx]
            lo = lows[cand_idx]

            # Candle direction
            is_bearish_candle = c < o
            is_bullish_candle = c > o

            # ── Bullish OB (from bullish BOS/CHoCH) ──
            if evt_direction == "bullish" and is_bearish_candle:
                if not _passes_body_filter(o, c, h, lo, config):
                    continue

                upper, lower = _compute_bounds(o, c, h, lo, "bullish", config)
                size = upper - lower
                midpoint = (upper + lower) / 2
                size_pct = (size / midpoint) * 100 if midpoint > 0 else 0

                if size_pct > config.max_block_size_pct:
                    continue

                key = ("bullish", cand_idx)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                obs.append(OrderBlock(
                    instrument=instrument, timeframe=timeframe,
                    direction="bullish",
                    upper_bound=upper, lower_bound=lower,
                    origin_candle_index=cand_idx,
                    creation_bar_index=evt_bar,
                    creation_timestamp=timestamps[evt_bar],
                    midpoint=midpoint, block_size=size, block_size_pct=size_pct,
                    related_ms_event_id=evt_id,
                    origin_open=o, origin_high=h, origin_low=lo, origin_close=c,
                    origin_volume=volumes[cand_idx] if volumes else 0.0,
                    metadata={"trigger_event": evt_type.lower(), "trigger_bar": evt_bar},
                ))
                ob_found = True
                break

            # ── Bearish OB (from bearish BOS/CHoCH) ──
            elif evt_direction == "bearish" and is_bullish_candle:
                if not _passes_body_filter(o, c, h, lo, config):
                    continue

                upper, lower = _compute_bounds(o, c, h, lo, "bearish", config)
                size = upper - lower
                midpoint = (upper + lower) / 2
                size_pct = (size / midpoint) * 100 if midpoint > 0 else 0

                if size_pct > config.max_block_size_pct:
                    continue

                key = ("bearish", cand_idx)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                obs.append(OrderBlock(
                    instrument=instrument, timeframe=timeframe,
                    direction="bearish",
                    upper_bound=upper, lower_bound=lower,
                    origin_candle_index=cand_idx,
                    creation_bar_index=evt_bar,
                    creation_timestamp=timestamps[evt_bar],
                    midpoint=midpoint, block_size=size, block_size_pct=size_pct,
                    related_ms_event_id=evt_id,
                    origin_open=o, origin_high=h, origin_low=lo, origin_close=c,
                    origin_volume=volumes[cand_idx] if volumes else 0.0,
                    metadata={"trigger_event": evt_type.lower(), "trigger_bar": evt_bar},
                ))
                ob_found = True
                break

        # If config allows, detect standalone OBs (no BOS/CHoCH required)
        if not ob_found and not config.require_bos_choch:
            _detect_standalone_obs(
                highs, lows, opens, closes, volumes, timestamps,
                evt_bar, evt_direction, instrument, timeframe,
                config, obs, seen_keys,
            )

    return obs


def _compute_bounds(
    open_: float, close: float, high: float, low: float,
    direction: str, config: OBConfig,
) -> tuple[float, float]:
    """Compute OB upper/lower bounds based on config."""
    if config.use_open_close_bounds:
        upper = max(open_, close)
        lower = min(open_, close)
    else:
        if direction == "bullish":
            # Upper = high (full sell-side absorbed), lower = open
            upper = high
            lower = open_
        else:
            # Upper = open, lower = low (full buy-side absorbed)
            upper = open_
            lower = low
    return upper, lower


def _passes_body_filter(
    open_: float, close: float, high: float, low: float, config: OBConfig,
) -> bool:
    """Check if candle meets minimum body size requirements."""
    if config.min_body_size_pct <= 0:
        return True
    candle_range = high - low
    if candle_range <= 0:
        return False
    body_size = abs(close - open_)
    body_pct = (body_size / candle_range) * 100
    return body_pct >= config.min_body_size_pct


def _detect_standalone_obs(
    highs, lows, opens, closes, volumes, timestamps,
    evt_bar, evt_direction, instrument, timeframe,
    config, obs, seen_keys,
):
    """Fallback: detect OBs without BOS/CHoCH (strong moves only)."""
    if evt_bar < 1:
        return
    cand_idx = evt_bar - 1
    o = opens[cand_idx]; c = closes[cand_idx]
    h = highs[cand_idx]; lo = lows[cand_idx]

    body_range = abs(c - o)
    total_range = h - lo
    if total_range <= 0:
        return
    # Require strong candle: body ≥ 60% of range
    if body_range / total_range < 0.6:
        return

    if evt_direction == "bullish" and c < o:
        direction = "bullish"
    elif evt_direction == "bearish" and c > o:
        direction = "bearish"
    else:
        return

    upper, lower = _compute_bounds(o, c, h, lo, direction, config)
    key = (direction, cand_idx)
    if key in seen_keys:
        return
    seen_keys.add(key)

    obs.append(OrderBlock(
        instrument=instrument, timeframe=timeframe,
        direction=direction, upper_bound=upper, lower_bound=lower,
        origin_candle_index=cand_idx, creation_bar_index=evt_bar,
        creation_timestamp=timestamps[evt_bar],
        related_ms_event_id=None,
        origin_open=o, origin_high=h, origin_low=lo, origin_close=c,
        origin_volume=volumes[cand_idx] if volumes else 0.0,
    ))


# ─── Lifecycle Management ────────────────────────────────────

@dataclass
class OBLifecycleEvent:
    """A lifecycle state change for an Order Block."""
    ob_id: int | None
    event_type: str  # created, first_touch, partially_mitigated, mitigated, invalidated
    bar_index: int
    timestamp: datetime
    mitigation_percentage: float
    metadata: dict = field(default_factory=dict)


def apply_ob_lifecycle(
    obs: list[OrderBlock],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    timestamps: list[datetime],
    config: OBConfig | None = None,
) -> tuple[list[OrderBlock], list[OBLifecycleEvent]]:
    """Apply lifecycle tracking to detected Order Blocks.

    Scans forward from creation to detect:
    - First touch of the OB zone
    - Partial mitigation
    - Full mitigation
    - Invalidation (price extends beyond)

    Returns updated OBs and lifecycle events.
    """
    if config is None:
        config = OBConfig()

    n = len(highs)
    events: list[OBLifecycleEvent] = []

    for ob in obs:
        # Creation event always emitted
        events.append(OBLifecycleEvent(
            ob_id=None, event_type="created",
            bar_index=ob.creation_bar_index,
            timestamp=ob.creation_timestamp,
            mitigation_percentage=0.0,
        ))

        start_idx = ob.creation_bar_index + 1
        ob_range = ob.upper_bound - ob.lower_bound
        if start_idx >= n or ob_range <= 0:
            continue

        mit_threshold = config.mitigation_threshold_pct
        inval_pct = config.invalidation_pct / 100.0
        max_age = config.expiration_bars
        use_close = config.mitigation_method == "close"

        for i in range(start_idx, n):
            # Max age check
            if max_age > 0 and (i - ob.creation_bar_index) > max_age:
                ob.status = OBStatus.INVALIDATED.value
                ob.invalidation_bar_index = i
                ob.invalidation_timestamp = timestamps[i]
                events.append(OBLifecycleEvent(
                    ob_id=None, event_type="invalidated",
                    bar_index=i, timestamp=timestamps[i],
                    mitigation_percentage=ob.mitigation_percentage,
                    metadata={"reason": "expired"},
                ))
                break

            price = closes[i] if use_close else (
                lows[i] if ob.direction == "bullish" else highs[i]
            )

            # Determine how much of the OB has been crossed
            if ob.direction == "bullish":
                # Price coming DOWN mitigates a bullish OB
                if price <= ob.lower_bound:
                    mit = 100.0
                elif price >= ob.upper_bound:
                    mit = 0.0
                else:
                    mit = ((ob.upper_bound - price) / ob_range) * 100
            else:
                # Price coming UP mitigates a bearish OB
                if price >= ob.upper_bound:
                    mit = 100.0
                elif price <= ob.lower_bound:
                    mit = 0.0
                else:
                    mit = ((price - ob.lower_bound) / ob_range) * 100

            mit = max(0.0, min(100.0, mit))
            ob.mitigation_percentage = max(ob.mitigation_percentage, mit)

            # First touch
            if mit > 0 and ob.first_touch_timestamp is None:
                ob.first_touch_timestamp = timestamps[i]
                ob.first_touch_bar_index = i
                if ob.status == OBStatus.ACTIVE.value:
                    ob.status = OBStatus.TOUCHED.value
                events.append(OBLifecycleEvent(
                    ob_id=None, event_type="first_touch",
                    bar_index=i, timestamp=timestamps[i],
                    mitigation_percentage=mit,
                ))

            # Partial mitigation
            if 0 < mit < mit_threshold:
                if ob.status == OBStatus.ACTIVE.value:
                    ob.status = OBStatus.TOUCHED.value
                elif ob.status == OBStatus.TOUCHED.value and mit >= 30:
                    ob.status = OBStatus.PARTIALLY_MITIGATED.value
                    events.append(OBLifecycleEvent(
                        ob_id=None, event_type="partially_mitigated",
                        bar_index=i, timestamp=timestamps[i],
                        mitigation_percentage=mit,
                    ))

            # Full mitigation
            if mit >= mit_threshold:
                ob.status = OBStatus.MITIGATED.value
                ob.mitigation_timestamp = timestamps[i]
                ob.mitigation_bar_index = i
                ob.mitigation_percentage = 100.0
                events.append(OBLifecycleEvent(
                    ob_id=None, event_type="mitigated",
                    bar_index=i, timestamp=timestamps[i],
                    mitigation_percentage=100.0,
                ))
                break

            # Invalidation: price extends beyond OB opposite direction
            if ob.direction == "bullish":
                if closes[i] > ob.upper_bound * (1 + inval_pct):
                    ob.status = OBStatus.INVALIDATED.value
                    ob.invalidation_timestamp = timestamps[i]
                    ob.invalidation_bar_index = i
                    events.append(OBLifecycleEvent(
                        ob_id=None, event_type="invalidated",
                        bar_index=i, timestamp=timestamps[i],
                        mitigation_percentage=ob.mitigation_percentage,
                        metadata={"reason": "price_extended_above"},
                    ))
                    break
            else:
                if closes[i] < ob.lower_bound * (1 - inval_pct):
                    ob.status = OBStatus.INVALIDATED.value
                    ob.invalidation_timestamp = timestamps[i]
                    ob.invalidation_bar_index = i
                    events.append(OBLifecycleEvent(
                        ob_id=None, event_type="invalidated",
                        bar_index=i, timestamp=timestamps[i],
                        mitigation_percentage=ob.mitigation_percentage,
                        metadata={"reason": "price_extended_below"},
                    ))
                    break

    events.sort(key=lambda e: (e.bar_index, _ob_event_priority(e.event_type)))
    return obs, events


def _ob_event_priority(event_type: str) -> int:
    return {"created": 0, "first_touch": 1, "partially_mitigated": 2, "mitigated": 3, "invalidated": 4}.get(event_type, 5)
