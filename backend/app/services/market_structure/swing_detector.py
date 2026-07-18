"""Swing Detector — identifies swing highs and lows from OHLCV bars.

All definitions are mathematical and deterministic:
- Swing High: bar i where high[i] > all highs in [i-N, i+N] (N=lookback)
- Swing Low:  bar i where low[i]  < all lows  in [i-N, i+N]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SwingPoint:
    """A detected swing high or low."""
    bar_index: int
    timestamp: datetime
    price: float
    swing_type: str  # "high" or "low"
    confirmed: bool = False
    confirmed_at_index: int | None = None

    def __repr__(self) -> str:
        return f"<Swing {self.swing_type} @{self.price} idx={self.bar_index}>"


def detect_swings(
    highs: list[float],
    lows: list[float],
    timestamps: list[datetime],
    lookback: int = 5,
    confirmation_bars: int = 1,
    min_distance_bars: int = 3,
    min_swing_size_pct: float = 0.0,
) -> list[SwingPoint]:
    """Detect swing highs and lows from price data.

    Args:
        highs: List of high prices (same length as lows/timestamps).
        lows: List of low prices.
        timestamps: List of bar timestamps.
        lookback: Bars to check left and right of candidate.
        confirmation_bars: Bars after candidate before confirming.
        min_distance_bars: Minimum bars between same-type swings.
        min_swing_size_pct: Minimum swing size as % of price (0=disabled).

    Returns:
        List of SwingPoint objects in chronological order.
    """
    n = len(highs)
    if n < 2 * lookback + 1:
        return []

    candidates: list[SwingPoint] = []

    # ─── Step 1: Find candidate swing points ─────────────────
    for i in range(lookback, n - lookback):
        # Check swing high
        h = highs[i]
        is_swing_high = all(
            highs[j] < h for j in range(i - lookback, i + lookback + 1) if j != i
        )
        if is_swing_high:
            candidates.append(SwingPoint(
                bar_index=i, timestamp=timestamps[i],
                price=h, swing_type="high",
            ))

        # Check swing low
        lo = lows[i]
        is_swing_low = all(
            lows[j] > lo for j in range(i - lookback, i + lookback + 1) if j != i
        )
        if is_swing_low:
            candidates.append(SwingPoint(
                bar_index=i, timestamp=timestamps[i],
                price=lo, swing_type="low",
            ))

    if not candidates:
        return []

    # ─── Step 2: Confirm swings (prevent repainting) ──────────
    for swing in candidates:
        if swing.bar_index + confirmation_bars < n:
            swing.confirmed = True
            swing.confirmed_at_index = swing.bar_index + confirmation_bars

    # ─── Step 3: Filter by minimum distance ───────────────────
    filtered: list[SwingPoint] = []
    last_high_idx = -min_distance_bars - 1
    last_low_idx = -min_distance_bars - 1

    for swing in sorted(candidates, key=lambda s: s.bar_index):
        if not swing.confirmed:
            continue
        if swing.swing_type == "high":
            if swing.bar_index - last_high_idx <= min_distance_bars:
                continue
            last_high_idx = swing.bar_index
        else:
            if swing.bar_index - last_low_idx <= min_distance_bars:
                continue
            last_low_idx = swing.bar_index
        filtered.append(swing)

    # ─── Step 4: Filter by minimum swing size ─────────────────
    if min_swing_size_pct > 0:
        result = []
        for swing in filtered:
            avg_price = (highs[swing.bar_index] + lows[swing.bar_index]) / 2
            if avg_price == 0:
                continue
            swing_size = abs(
                highs[swing.bar_index] - lows[swing.bar_index]
            ) / avg_price * 100
            if swing_size >= min_swing_size_pct:
                result.append(swing)
        return result

    return filtered
