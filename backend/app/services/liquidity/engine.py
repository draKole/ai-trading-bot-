"""Liquidity Detection Engine — identifies liquidity levels and events.

All definitions are deterministic and mathematical.
No subjective or AI-based interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from app.services.liquidity.session_engine import (
    SessionEngine, SessionConfig, SessionName, SessionBoundary, SESSION_ORDER,
)
from app.services.market_structure.swing_detector import SwingPoint


# ─── Liquidity Types ─────────────────────────────────────────

class LiquidityType(str, Enum):
    PDH = "pdh"                  # Previous Day High
    PDL = "pdl"                  # Previous Day Low
    PWH = "pwh"                  # Previous Week High
    PWL = "pwl"                  # Previous Week Low
    PMH = "pmh"                  # Previous Month High
    PML = "pml"                  # Previous Month Low
    ASIA_HIGH = "asia_high"
    ASIA_LOW = "asia_low"
    LONDON_HIGH = "london_high"
    LONDON_LOW = "london_low"
    NY_HIGH = "ny_high"
    NY_LOW = "ny_low"
    EQUAL_HIGHS = "equal_highs"
    EQUAL_LOWS = "equal_lows"
    SWING_HIGH_LIQ = "swing_high_liq"   # Liquidity above a swing high
    SWING_LOW_LIQ = "swing_low_liq"     # Liquidity below a swing low
    INTERNAL_HIGH = "internal_high"     # Internal range high
    INTERNAL_LOW = "internal_low"       # Internal range low


class LiquidityEventType(str, Enum):
    APPROACHED = "approached"     # Within threshold % of level
    TOUCHED = "touched"           # Price exactly touches level
    SWEPT = "swept"               # Wicks through then reverses
    REJECTED = "rejected"         # Touches + strong reversal
    BROKEN = "broken"             # Closes beyond level
    INVALIDATED = "invalidated"   # Level superseded/removed


# ─── Configuration ───────────────────────────────────────────

@dataclass
class LiquidityConfig:
    """Configuration for liquidity detection.

    Attributes:
        equal_level_tolerance_pct: Max % difference between two levels to
            consider them "equal" (e.g., 0.05 = 0.05%). Default: 0.05.
        equal_level_min_bars: Minimum bars between equal highs/lows.
            Default: 3.
        approach_threshold_pct: Distance % to trigger "approached".
            Default: 0.1 (0.1%).
        sweep_wick_pct: Minimum wick % beyond level for a sweep.
            Default: 0.02.
        break_requires_close: Whether "broken" requires close beyond level.
            Default: True.
        rejection_reversal_pct: Minimum reversal % from level for "rejected".
            Default: 0.15.
        lookback_bars: Bars to look back for PD/PS levels. Default: 5000.
        session_config: Session engine configuration.
    """
    equal_level_tolerance_pct: float = 0.05
    equal_level_min_bars: int = 3
    approach_threshold_pct: float = 0.1
    sweep_wick_pct: float = 0.02
    break_requires_close: bool = True
    rejection_reversal_pct: float = 0.15
    lookback_bars: int = 5000

    session_config: SessionConfig = field(default_factory=SessionConfig)

    def to_dict(self) -> dict:
        return {
            "equal_level_tolerance_pct": self.equal_level_tolerance_pct,
            "equal_level_min_bars": self.equal_level_min_bars,
            "approach_threshold_pct": self.approach_threshold_pct,
            "sweep_wick_pct": self.sweep_wick_pct,
            "break_requires_close": self.break_requires_close,
            "rejection_reversal_pct": self.rejection_reversal_pct,
            "lookback_bars": self.lookback_bars,
            "session_config": self.session_config.to_dict(),
        }


# ─── Data Classes ────────────────────────────────────────────

@dataclass
class LiquidityLevel:
    """A detected liquidity level."""
    level_type: LiquidityType
    price: float
    source_bar_index: int          # Bar that defined this level
    source_timestamp: datetime      # Timestamp of defining bar
    session: SessionName | None = None
    metadata: dict = field(default_factory=dict)

    def __hash__(self):
        return hash((self.level_type.value, round(self.price, 6), self.source_bar_index))


@dataclass
class LiquidityEvent:
    """An interaction between price and a liquidity level."""
    level: LiquidityLevel
    event_type: LiquidityEventType
    bar_index: int
    timestamp: datetime
    bar_high: float
    bar_low: float
    bar_close: float
    direction: str | None = None  # "bullish" or "bearish"
    distance_pct: float = 0.0
    metadata: dict = field(default_factory=dict)


# ─── Liquidity Engine ────────────────────────────────────────

class LiquidityEngine:
    """Detects liquidity levels from bar data and market structure.

    Usage:
        engine = LiquidityEngine(config)
        levels = engine.detect_levels(bars, swings, instrument)
        events = engine.detect_events(levels, bars)
    """

    def __init__(self, config: LiquidityConfig | None = None):
        self.config = config or LiquidityConfig()
        self.session_engine = SessionEngine(self.config.session_config)

    # ─── Level Detection ─────────────────────────────────────

    def detect_levels(
        self,
        bars: list,
        swings: list[SwingPoint] | None = None,
        instrument: str = "",
    ) -> list[LiquidityLevel]:
        """Detect all liquidity levels from bar data.

        Args:
            bars: List of OHLCVBar objects in chronological order.
            swings: Pre-detected swing points (optional, for swing/internal liquidity).
            instrument: Instrument symbol.

        Returns:
            List of LiquidityLevel objects.
        """
        if not bars:
            return []

        levels: list[LiquidityLevel] = []
        n = len(bars)

        # ── Previous Period Levels ────────────────────────────
        levels.extend(self._detect_previous_day_levels(bars, n))
        levels.extend(self._detect_previous_week_levels(bars, n))
        levels.extend(self._detect_previous_month_levels(bars, n))

        # ── Session Levels ────────────────────────────────────
        levels.extend(self._detect_session_levels(bars, n))

        # ── Equal Highs/Lows ─────────────────────────────────
        if swings:
            levels.extend(self._detect_equal_levels(swings))

        # ── Swing Liquidity ──────────────────────────────────
        if swings:
            levels.extend(self._detect_swing_liquidity(swings, bars, n))

        # ── Internal Liquidity ───────────────────────────────
        if swings and len(swings) >= 2:
            levels.extend(self._detect_internal_liquidity(swings, bars, n))

        # Sort by source_bar_index
        levels.sort(key=lambda l: l.source_bar_index)
        return levels

    def _detect_previous_day_levels(
        self, bars: list, n: int,
    ) -> list[LiquidityLevel]:
        """Detect PDH/PDL from the previous trading day."""
        levels = []
        if n < 2:
            return levels

        last_bar = bars[-1]
        last_ts = last_bar.timestamp

        # Find previous day's bars
        prev_day_bars = self._get_previous_period_bars(
            bars, last_ts, period="day",
        )
        if not prev_day_bars:
            return levels

        pd_high = max(b.high for b in prev_day_bars)
        pd_low = min(b.low for b in prev_day_bars)

        levels.append(LiquidityLevel(
            level_type=LiquidityType.PDH,
            price=pd_high,
            source_bar_index=prev_day_bars[-1].bar_index if hasattr(prev_day_bars[-1], 'bar_index') else n - 1,
            source_timestamp=prev_day_bars[-1].timestamp,
            metadata={"period_start": prev_day_bars[0].timestamp.isoformat(),
                      "period_end": prev_day_bars[-1].timestamp.isoformat()},
        ))
        levels.append(LiquidityLevel(
            level_type=LiquidityType.PDL,
            price=pd_low,
            source_bar_index=prev_day_bars[-1].bar_index if hasattr(prev_day_bars[-1], 'bar_index') else n - 1,
            source_timestamp=prev_day_bars[-1].timestamp,
            metadata={"period_start": prev_day_bars[0].timestamp.isoformat(),
                      "period_end": prev_day_bars[-1].timestamp.isoformat()},
        ))
        return levels

    def _detect_previous_week_levels(
        self, bars: list, n: int,
    ) -> list[LiquidityLevel]:
        """Detect PWH/PWL from the previous trading week."""
        levels = []
        if n < 2:
            return levels

        last_ts = bars[-1].timestamp
        prev_week_bars = self._get_previous_period_bars(bars, last_ts, period="week")
        if not prev_week_bars:
            return levels

        pw_high = max(b.high for b in prev_week_bars)
        pw_low = min(b.low for b in prev_week_bars)

        levels.append(LiquidityLevel(
            level_type=LiquidityType.PWH,
            price=pw_high,
            source_bar_index=prev_week_bars[-1].bar_index if hasattr(prev_week_bars[-1], 'bar_index') else n - 1,
            source_timestamp=prev_week_bars[-1].timestamp,
        ))
        levels.append(LiquidityLevel(
            level_type=LiquidityType.PWL,
            price=pw_low,
            source_bar_index=prev_week_bars[-1].bar_index if hasattr(prev_week_bars[-1], 'bar_index') else n - 1,
            source_timestamp=prev_week_bars[-1].timestamp,
        ))
        return levels

    def _detect_previous_month_levels(
        self, bars: list, n: int,
    ) -> list[LiquidityLevel]:
        """Detect PMH/PML from the previous calendar month."""
        levels = []
        if n < 2:
            return levels

        last_ts = bars[-1].timestamp
        prev_month_bars = self._get_previous_period_bars(bars, last_ts, period="month")
        if not prev_month_bars:
            return levels

        pm_high = max(b.high for b in prev_month_bars)
        pm_low = min(b.low for b in prev_month_bars)

        levels.append(LiquidityLevel(
            level_type=LiquidityType.PMH,
            price=pm_high,
            source_bar_index=prev_month_bars[-1].bar_index if hasattr(prev_month_bars[-1], 'bar_index') else n - 1,
            source_timestamp=prev_month_bars[-1].timestamp,
        ))
        levels.append(LiquidityLevel(
            level_type=LiquidityType.PML,
            price=pm_low,
            source_bar_index=prev_month_bars[-1].bar_index if hasattr(prev_month_bars[-1], 'bar_index') else n - 1,
            source_timestamp=prev_month_bars[-1].timestamp,
        ))
        return levels

    def _get_previous_period_bars(
        self, bars: list, reference_ts: datetime, period: str,
    ) -> list:
        """Get bars from the previous day/week/month.

        Args:
            bars: All bars in chronological order.
            reference_ts: Reference timestamp (typically last bar).
            period: "day", "week", or "month".
        """
        if period == "day":
            # Previous calendar day
            prev_day = reference_ts.date() - timedelta(days=1)
            return [
                b for b in bars
                if b.timestamp.date() == prev_day
            ]
        elif period == "week":
            # Previous ISO week
            current_monday = reference_ts.date() - timedelta(days=reference_ts.weekday())
            prev_monday = current_monday - timedelta(days=7)
            prev_sunday = current_monday - timedelta(days=1)
            return [
                b for b in bars
                if prev_monday <= b.timestamp.date() <= prev_sunday
            ]
        elif period == "month":
            # Previous calendar month
            if reference_ts.month == 1:
                prev_month = 12
                prev_year = reference_ts.year - 1
            else:
                prev_month = reference_ts.month - 1
                prev_year = reference_ts.year
            return [
                b for b in bars
                if b.timestamp.year == prev_year and b.timestamp.month == prev_month
            ]
        return []

    def _detect_session_levels(
        self, bars: list, n: int,
    ) -> list[LiquidityLevel]:
        """Detect session highs/lows for each configured session."""
        levels = []
        # Group bars by session
        session_bars: dict[SessionName, list] = {}

        for i, bar in enumerate(bars):
            session = self.session_engine.get_session(bar.timestamp)
            if session:
                if session not in session_bars:
                    session_bars[session] = []
                # Attach bar index for reference
                bar._idx = i
                session_bars[session].append(bar)

        session_type_map = {
            SessionName.ASIA: (LiquidityType.ASIA_HIGH, LiquidityType.ASIA_LOW),
            SessionName.LONDON: (LiquidityType.LONDON_HIGH, LiquidityType.LONDON_LOW),
            SessionName.NY_AM: (LiquidityType.NY_HIGH, LiquidityType.NY_LOW),
            SessionName.NY_PM: (LiquidityType.NY_HIGH, LiquidityType.NY_LOW),
        }

        for session, s_bars in session_bars.items():
            if not s_bars:
                continue
            hi_type, lo_type = session_type_map[session]
            s_high = max(b.high for b in s_bars)
            s_low = min(b.low for b in s_bars)
            last_bar = s_bars[-1]
            src_idx = getattr(last_bar, '_idx', n - 1)

            levels.append(LiquidityLevel(
                level_type=hi_type,
                price=s_high,
                source_bar_index=src_idx,
                source_timestamp=last_bar.timestamp,
                session=session,
                metadata={"bar_count": len(s_bars)},
            ))
            levels.append(LiquidityLevel(
                level_type=lo_type,
                price=s_low,
                source_bar_index=src_idx,
                source_timestamp=last_bar.timestamp,
                session=session,
                metadata={"bar_count": len(s_bars)},
            ))

        return levels

    def _detect_equal_levels(
        self, swings: list[SwingPoint],
    ) -> list[LiquidityLevel]:
        """Detect equal highs and equal lows from swing points."""
        levels = []
        tol = self.config.equal_level_tolerance_pct / 100.0
        min_bars = self.config.equal_level_min_bars

        swing_highs = [s for s in swings if s.swing_type == "high"]
        swing_lows = [s for s in swings if s.swing_type == "low"]

        # Equal highs: two or more swing highs at approximately the same price
        for i in range(len(swing_highs)):
            cluster = [swing_highs[i]]
            for j in range(i + 1, len(swing_highs)):
                price_diff_pct = abs(
                    swing_highs[j].price - swing_highs[i].price
                ) / swing_highs[i].price
                if price_diff_pct <= tol:
                    if swing_highs[j].bar_index - cluster[-1].bar_index >= min_bars:
                        cluster.append(swing_highs[j])
            if len(cluster) >= 2:
                avg_price = sum(s.price for s in cluster) / len(cluster)
                levels.append(LiquidityLevel(
                    level_type=LiquidityType.EQUAL_HIGHS,
                    price=avg_price,
                    source_bar_index=cluster[-1].bar_index,
                    source_timestamp=cluster[-1].timestamp,
                    metadata={
                        "count": len(cluster),
                        "prices": [s.price for s in cluster],
                        "bar_indices": [s.bar_index for s in cluster],
                    },
                ))

        # Equal lows
        for i in range(len(swing_lows)):
            cluster = [swing_lows[i]]
            for j in range(i + 1, len(swing_lows)):
                price_diff_pct = abs(
                    swing_lows[j].price - swing_lows[i].price
                ) / swing_lows[i].price
                if price_diff_pct <= tol:
                    if swing_lows[j].bar_index - cluster[-1].bar_index >= min_bars:
                        cluster.append(swing_lows[j])
            if len(cluster) >= 2:
                avg_price = sum(s.price for s in cluster) / len(cluster)
                levels.append(LiquidityLevel(
                    level_type=LiquidityType.EQUAL_LOWS,
                    price=avg_price,
                    source_bar_index=cluster[-1].bar_index,
                    source_timestamp=cluster[-1].timestamp,
                    metadata={
                        "count": len(cluster),
                        "prices": [s.price for s in cluster],
                        "bar_indices": [s.bar_index for s in cluster],
                    },
                ))

        return levels

    def _detect_swing_liquidity(
        self, swings: list[SwingPoint], bars: list, n: int,
    ) -> list[LiquidityLevel]:
        """Liquidity resting above swing highs and below swing lows."""
        levels = []

        for swing in swings:
            # Skip very recent swings (within last lookback bars of end)
            if n - swing.bar_index < 5:
                continue

            if swing.swing_type == "high":
                levels.append(LiquidityLevel(
                    level_type=LiquidityType.SWING_HIGH_LIQ,
                    price=swing.price,
                    source_bar_index=swing.bar_index,
                    source_timestamp=swing.timestamp,
                    metadata={"swing_type": "high"},
                ))
            else:
                levels.append(LiquidityLevel(
                    level_type=LiquidityType.SWING_LOW_LIQ,
                    price=swing.price,
                    source_bar_index=swing.bar_index,
                    source_timestamp=swing.timestamp,
                    metadata={"swing_type": "low"},
                ))

        return levels

    def _detect_internal_liquidity(
        self, swings: list[SwingPoint], bars: list, n: int,
    ) -> list[LiquidityLevel]:
        """Internal liquidity: midpoints and range boundaries within structure."""
        levels = []
        swing_highs = [s for s in swings if s.swing_type == "high"]
        swing_lows = [s for s in swings if s.swing_type == "low"]

        if len(swing_highs) >= 2 and len(swing_lows) >= 1:
            # Internal range high = most recent lower high (or first high if uptrend)
            recent_highs = sorted(swing_highs[-3:], key=lambda s: s.bar_index)
            if recent_highs:
                levels.append(LiquidityLevel(
                    level_type=LiquidityType.INTERNAL_HIGH,
                    price=recent_highs[-1].price,
                    source_bar_index=recent_highs[-1].bar_index,
                    source_timestamp=recent_highs[-1].timestamp,
                ))

        if len(swing_lows) >= 2 and len(swing_highs) >= 1:
            recent_lows = sorted(swing_lows[-3:], key=lambda s: s.bar_index)
            if recent_lows:
                levels.append(LiquidityLevel(
                    level_type=LiquidityType.INTERNAL_LOW,
                    price=recent_lows[-1].price,
                    source_bar_index=recent_lows[-1].bar_index,
                    source_timestamp=recent_lows[-1].timestamp,
                ))

        return levels

    # ─── Event Detection ──────────────────────────────────────

    def detect_events(
        self,
        levels: list[LiquidityLevel],
        bars: list,
    ) -> list[LiquidityEvent]:
        """Detect price interactions with liquidity levels.

        For each bar, check if it approaches, touches, sweeps, rejects,
        or breaks any active liquidity level.
        """
        if not levels or not bars:
            return []

        events: list[LiquidityEvent] = []
        approach_thresh = self.config.approach_threshold_pct / 100.0
        sweep_thresh = self.config.sweep_wick_pct / 100.0
        rejection_pct = self.config.rejection_reversal_pct / 100.0
        break_close = self.config.break_requires_close

        # Only consider levels active after they were formed
        levels_by_index: dict[int, list[LiquidityLevel]] = {}
        for lvl in levels:
            idx = lvl.source_bar_index
            if idx not in levels_by_index:
                levels_by_index[idx] = []
            levels_by_index[idx].append(lvl)

        active_levels: list[LiquidityLevel] = []
        swept_levels: set[tuple[str, float]] = set()  # track swept levels

        for i, bar in enumerate(bars):
            # Activate levels that are now formed
            if i in levels_by_index:
                active_levels.extend(levels_by_index[i])

            bar_high = bar.high
            bar_low = bar.low
            bar_close = bar.close
            bar_open = bar.open
            bar_mid = (bar_high + bar_low) / 2

            for lvl in active_levels:
                lvl_key = (lvl.level_type.value, round(lvl.price, 6))
                price = lvl.price
                if price == 0:
                    continue

                distance_pct = min(
                    abs(bar_high - price) / price,
                    abs(bar_low - price) / price,
                )

                # ── Check for touch (high/low crosses the level) ──
                touched = bar_low <= price <= bar_high

                if touched:
                    # Swept: wick goes through but body stays on original side
                    body_above = min(bar_open, bar_close) > price
                    body_below = max(bar_open, bar_close) < price

                    if body_below and bar_high - price > sweep_thresh * price:
                        # Price wicked above but closed below = sweep high
                        if lvl_key not in swept_levels:
                            swept_levels.add(lvl_key)
                            events.append(LiquidityEvent(
                                level=lvl,
                                event_type=LiquidityEventType.SWEPT,
                                bar_index=i, timestamp=bar.timestamp,
                                bar_high=bar_high, bar_low=bar_low,
                                bar_close=bar_close,
                                direction="bearish",
                                distance_pct=distance_pct,
                                metadata={"wick_pct": (bar_high - price) / price * 100},
                            ))
                        continue

                    if body_above and price - bar_low > sweep_thresh * price:
                        if lvl_key not in swept_levels:
                            swept_levels.add(lvl_key)
                            events.append(LiquidityEvent(
                                level=lvl,
                                event_type=LiquidityEventType.SWEPT,
                                bar_index=i, timestamp=bar.timestamp,
                                bar_high=bar_high, bar_low=bar_low,
                                bar_close=bar_close,
                                direction="bullish",
                                distance_pct=distance_pct,
                                metadata={"wick_pct": (price - bar_low) / price * 100},
                            ))
                        continue

                    # Rejected: body crosses level (open above, close below or vice versa)
                    # with strong closing momentum away from level
                    open_above = bar_open > price
                    close_below = bar_close < price
                    open_below = bar_open < price
                    close_above = bar_close > price

                    if open_above and close_below:
                        reversal = (price - bar_close) / price
                        if reversal >= rejection_pct:
                            events.append(LiquidityEvent(
                                level=lvl,
                                event_type=LiquidityEventType.REJECTED,
                                bar_index=i, timestamp=bar.timestamp,
                                bar_high=bar_high, bar_low=bar_low,
                                bar_close=bar_close,
                                direction="bearish",
                                distance_pct=distance_pct,
                            ))
                            continue

                    if open_below and close_above:
                        reversal = (bar_close - price) / price
                        if reversal >= rejection_pct:
                            events.append(LiquidityEvent(
                                level=lvl,
                                event_type=LiquidityEventType.REJECTED,
                                bar_index=i, timestamp=bar.timestamp,
                                bar_high=bar_high, bar_low=bar_low,
                                bar_close=bar_close,
                                direction="bullish",
                                distance_pct=distance_pct,
                            ))
                            continue

                    # Regular touch
                    events.append(LiquidityEvent(
                        level=lvl,
                        event_type=LiquidityEventType.TOUCHED,
                        bar_index=i, timestamp=bar.timestamp,
                        bar_high=bar_high, bar_low=bar_low,
                        bar_close=bar_close,
                        distance_pct=distance_pct,
                    ))
                    continue

                # ── Approached (close but not touching) ──
                if distance_pct <= approach_thresh:
                    events.append(LiquidityEvent(
                        level=lvl,
                        event_type=LiquidityEventType.APPROACHED,
                        bar_index=i, timestamp=bar.timestamp,
                        bar_high=bar_high, bar_low=bar_low,
                        bar_close=bar_close,
                        distance_pct=distance_pct,
                    ))
                    continue

                # ── Broken: close beyond level ──
                if break_close and bar_close > price and bar_low > price:
                    # Close completely above a resistance level
                    events.append(LiquidityEvent(
                        level=lvl,
                        event_type=LiquidityEventType.BROKEN,
                        bar_index=i, timestamp=bar.timestamp,
                        bar_high=bar_high, bar_low=bar_low,
                        bar_close=bar_close,
                        direction="bullish",
                        distance_pct=distance_pct,
                    ))
                elif break_close and bar_close < price and bar_high < price:
                    events.append(LiquidityEvent(
                        level=lvl,
                        event_type=LiquidityEventType.BROKEN,
                        bar_index=i, timestamp=bar.timestamp,
                        bar_high=bar_high, bar_low=bar_low,
                        bar_close=bar_close,
                        direction="bearish",
                        distance_pct=distance_pct,
                    ))

        return events
