"""Structure Analyzer — detects HH, HL, LH, LL, BOS, CHoCH, MSS from swings.

All definitions are mathematical, consuming swing points and OHLCV data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StructureEventType(str, Enum):
    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"
    HIGHER_HIGH = "higher_high"
    HIGHER_LOW = "higher_low"
    LOWER_HIGH = "lower_high"
    LOWER_LOW = "lower_low"
    BOS = "bos"                 # Break of Structure
    CHOCH = "choch"             # Change of Character
    MSS = "mss"                 # Market Structure Shift


@dataclass
class StructureEvent:
    """A detected market structure event."""
    instrument: str
    timeframe: str
    timestamp: datetime
    event_type: StructureEventType
    price_level: float
    direction: str | None = None  # "bullish" or "bearish"
    bar_index: int = 0
    parent_swing: SwingPoint_ref | None = None
    broken_level: float | None = None
    broken_level_source: str | None = None  # "swing_high", "swing_low"
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"<{self.event_type.value} {self.direction or ''} "
            f"@{self.price_level:.2f}>"
        )


# Forward reference for SwingPoint
from app.services.market_structure.swing_detector import SwingPoint as SwingPoint_ref


def analyze_structure(
    swings: list[SwingPoint_ref],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    opens: list[float],
    timestamps: list[datetime],
    instrument: str,
    timeframe: str,
    config: dict | None = None,
) -> list[StructureEvent]:
    """Analyze swing points to detect HH, HL, LH, LL, BOS, CHoCH, MSS.

    Args:
        swings: Chronological list of detected swing points.
        highs/lows/closes/opens: OHLC arrays for the entire bar series.
        timestamps: Bar timestamps.
        instrument: Instrument symbol.
        timeframe: Timeframe string.
        config: Dict of configuration parameters (bos_requires_close, etc.).

    Returns:
        Chronological list of StructureEvent objects.
    """
    if config is None:
        config = {}

    bos_close = config.get("bos_requires_close", True)
    choch_close = config.get("choch_requires_close", True)
    use_body = config.get("use_body_for_breaks", False)

    events: list[StructureEvent] = []

    if len(swings) < 2:
        # Just emit the swing events themselves
        for s in swings:
            events.append(StructureEvent(
                instrument=instrument, timeframe=timeframe,
                timestamp=s.timestamp,
                event_type=(
                    StructureEventType.SWING_HIGH
                    if s.swing_type == "high"
                    else StructureEventType.SWING_LOW
                ),
                price_level=s.price,
                bar_index=s.bar_index,
            ))
        return events

    # ─── Step 1: Emit swing events + classify HH/HL/LH/LL ─────
    last_swing_high: SwingPoint_ref | None = None
    last_swing_low: SwingPoint_ref | None = None
    swing_event_map: dict[int, int] = {}  # bar_index → event index

    for s in swings:
        if s.swing_type == "high":
            event_type = StructureEventType.SWING_HIGH
            if last_swing_high is not None:
                if s.price > last_swing_high.price:
                    event_type = StructureEventType.HIGHER_HIGH
                else:
                    event_type = StructureEventType.LOWER_HIGH
            last_swing_high = s
        else:
            event_type = StructureEventType.SWING_LOW
            if last_swing_low is not None:
                if s.price > last_swing_low.price:
                    event_type = StructureEventType.HIGHER_LOW
                else:
                    event_type = StructureEventType.LOWER_LOW
            last_swing_low = s

        evt = StructureEvent(
            instrument=instrument, timeframe=timeframe,
            timestamp=s.timestamp,
            event_type=event_type,
            price_level=s.price,
            direction="bullish" if "HIGHER" in event_type.value.upper() or event_type in (
                StructureEventType.SWING_HIGH, StructureEventType.SWING_LOW
            ) else "bearish" if "LOWER" in event_type.value.upper() else None,
            bar_index=s.bar_index,
        )
        events.append(evt)
        swing_event_map[s.bar_index] = len(events) - 1

    # ─── Step 2: Detect BOS, CHoCH, MSS ──────────────────────
    # Get swing highs and lows in chronological order
    swing_highs = [s for s in swings if s.swing_type == "high"]
    swing_lows = [s for s in swings if s.swing_type == "low"]

    # We iterate through ALL bars. For each bar, we check if it breaks
    # the most recent unbroken swing level.

    # Track which swings are still "active" (unbroken)
    unbroken_highs: list[SwingPoint_ref] = []
    unbroken_lows: list[SwingPoint_ref] = []

    # Track the prevailing trend for CHoCH detection
    # We determine trend from the sequence of HH/HL vs LH/LL
    trend: str = "neutral"  # "bullish", "bearish", "neutral"

    for s in swings:
        if s.swing_type == "high":
            unbroken_highs.append(s)
            # Remove any lows that are below this high (they're broken)
            unbroken_lows = [
                lo for lo in unbroken_lows
                if lo.price > s.price  # only keep lows ABOVE this high's price
            ]
        else:
            unbroken_lows.append(s)
            unbroken_highs = [
                hi for hi in unbroken_highs
                if hi.price < s.price
            ]

    # Now scan ALL bars for breaks of the nearest unbroken swing
    if len(swings) >= 2:
        # Determine trend
        trend = _determine_trend(swings)

        # Find BOS and CHoCH
        bos_choch_events = _detect_bos_choch(
            swings=swings,
            highs=highs,
            lows=lows,
            closes=closes,
            opens=opens,
            timestamps=timestamps,
            instrument=instrument,
            timeframe=timeframe,
            bos_requires_close=bos_close,
            choch_requires_close=choch_close,
            use_body=use_body,
            trend=trend,
        )
        events.extend(bos_choch_events)

    # Sort all events by bar_index, then by event_type priority
    type_priority = {
        StructureEventType.MSS: 4,
        StructureEventType.CHOCH: 3,
        StructureEventType.BOS: 2,
        StructureEventType.HIGHER_HIGH: 1,
        StructureEventType.HIGHER_LOW: 1,
        StructureEventType.LOWER_HIGH: 1,
        StructureEventType.LOWER_LOW: 1,
        StructureEventType.SWING_HIGH: 0,
        StructureEventType.SWING_LOW: 0,
    }

    events.sort(key=lambda e: (e.bar_index, type_priority.get(e.event_type, 0)))

    return events


def _determine_trend(swings: list[SwingPoint_ref]) -> str:
    """Determine the prevailing trend from swing sequence."""
    highs = [s for s in swings if s.swing_type == "high"]
    lows = [s for s in swings if s.swing_type == "low"]

    # Count HH vs LH
    hh_count = sum(
        1 for i in range(1, len(highs)) if highs[i].price > highs[i - 1].price
    )
    lh_count = sum(
        1 for i in range(1, len(highs)) if highs[i].price < highs[i - 1].price
    )
    hl_count = sum(
        1 for i in range(1, len(lows)) if lows[i].price > lows[i - 1].price
    )
    ll_count = sum(
        1 for i in range(1, len(lows)) if lows[i].price < lows[i - 1].price
    )

    bullish_score = hh_count + hl_count
    bearish_score = lh_count + ll_count

    if bullish_score > bearish_score:
        return "bullish"
    elif bearish_score > bullish_score:
        return "bearish"
    # If tied or no data, check last swing direction
    if len(highs) >= 2:
        if highs[-1].price > highs[-2].price:
            return "bullish"
        elif highs[-1].price < highs[-2].price:
            return "bearish"
    if len(lows) >= 2:
        if lows[-1].price > lows[-2].price:
            return "bullish"
        elif lows[-1].price < lows[-2].price:
            return "bearish"
    return "neutral"


def _detect_bos_choch(
    swings: list[SwingPoint_ref],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    opens: list[float],
    timestamps: list[datetime],
    instrument: str,
    timeframe: str,
    bos_requires_close: bool,
    choch_requires_close: bool,
    use_body: bool,
    trend: str,
) -> list[StructureEvent]:
    """Detect BOS, CHoCH, and MSS events.

    BOS: Break of a prior swing level IN the direction of the trend.
        - Bullish BOS: In uptrend, break above prior swing high.
        - Bearish BOS: In downtrend, break below prior swing low.

    CHoCH: Break of a prior swing level AGAINST the prevailing trend.
        - Bullish CHoCH: In downtrend, break above a prior swing high.
        - Bearish CHoCH: In uptrend, break below a prior swing low.

    MSS: A CHoCH that also closes beyond the broken level.
    """
    events: list[StructureEvent] = []
    n = len(highs)

    # Get swing points
    swing_highs = [s for s in swings if s.swing_type == "high"]
    swing_lows = [s for s in swings if s.swing_type == "low"]

    # Track which levels have been broken to avoid duplicates
    broken_high_levels: set[float] = set()
    broken_low_levels: set[float] = set()

    # For each swing level, scan forward to see if it gets broken
    all_swings_chrono = sorted(swings, key=lambda s: s.bar_index)

    for swing in all_swings_chrono:
        level_price = swing.price
        level_idx = swing.bar_index

        # Scan bars after the swing
        for i in range(level_idx + 1, n):
            if use_body:
                break_price_high = max(opens[i], closes[i])
                break_price_low = min(opens[i], closes[i])
            else:
                break_price_high = highs[i]
                break_price_low = lows[i]

            if swing.swing_type == "high":
                # Price breaks ABOVE a swing high
                if break_price_high > level_price and level_price not in broken_high_levels:
                    broken_high_levels.add(level_price)

                    if bos_requires_close and closes[i] <= level_price:
                        continue  # No close confirmation

                    if trend == "bullish":
                        # Breaking above a high in uptrend = BOS
                        events.append(StructureEvent(
                            instrument=instrument,
                            timeframe=timeframe,
                            timestamp=timestamps[i],
                            event_type=StructureEventType.BOS,
                            price_level=level_price,
                            direction="bullish",
                            bar_index=i,
                            broken_level=level_price,
                            broken_level_source="swing_high",
                            metadata={"break_bar_index": i, "swing_bar_index": level_idx},
                        ))
                    else:
                        # Breaking above a high in downtrend = CHoCH
                        evt_type = StructureEventType.CHOCH
                        # MSS if it also closes above
                        if closes[i] > level_price and choch_requires_close:
                            evt_type = StructureEventType.MSS
                        events.append(StructureEvent(
                            instrument=instrument,
                            timeframe=timeframe,
                            timestamp=timestamps[i],
                            event_type=evt_type,
                            price_level=level_price,
                            direction="bullish",
                            bar_index=i,
                            broken_level=level_price,
                            broken_level_source="swing_high",
                            metadata={"break_bar_index": i, "swing_bar_index": level_idx},
                        ))
                    break  # Only detect first break

            else:  # swing_type == "low"
                # Price breaks BELOW a swing low
                if break_price_low < level_price and level_price not in broken_low_levels:
                    broken_low_levels.add(level_price)

                    if bos_requires_close and closes[i] >= level_price:
                        continue  # No close confirmation

                    if trend == "bearish":
                        # Breaking below a low in downtrend = BOS
                        events.append(StructureEvent(
                            instrument=instrument,
                            timeframe=timeframe,
                            timestamp=timestamps[i],
                            event_type=StructureEventType.BOS,
                            price_level=level_price,
                            direction="bearish",
                            bar_index=i,
                            broken_level=level_price,
                            broken_level_source="swing_low",
                            metadata={"break_bar_index": i, "swing_bar_index": level_idx},
                        ))
                    else:
                        evt_type = StructureEventType.CHOCH
                        if closes[i] < level_price and choch_requires_close:
                            evt_type = StructureEventType.MSS
                        events.append(StructureEvent(
                            instrument=instrument,
                            timeframe=timeframe,
                            timestamp=timestamps[i],
                            event_type=evt_type,
                            price_level=level_price,
                            direction="bearish",
                            bar_index=i,
                            broken_level=level_price,
                            broken_level_source="swing_low",
                            metadata={"break_bar_index": i, "swing_bar_index": level_idx},
                        ))
                    break

    return events
