"""Market Structure Engine — main entry point.

Consumes OHLCV bars, produces market structure events.
Delegates to swing_detector and structure_analyzer.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from app.services.market_structure.config import MarketStructureConfig
from app.services.market_structure.swing_detector import detect_swings, SwingPoint
from app.services.market_structure.structure_analyzer import (
    analyze_structure,
    StructureEvent,
    StructureEventType,
)

logger = structlog.get_logger()


class MarketStructureEngine:
    """Detect market structure from OHLCV bar data.

    Usage:
        engine = MarketStructureEngine(config)
        events = engine.analyze(bars)
    """

    def __init__(self, config: MarketStructureConfig | None = None):
        self.config = config or MarketStructureConfig()

    def analyze_bars(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        opens: list[float],
        timestamps: list[datetime],
        instrument: str,
        timeframe: str,
    ) -> list[StructureEvent]:
        """Run full market structure analysis on a bar series.

        Args:
            highs/lows/closes/opens: OHLC arrays (same length).
            timestamps: Bar timestamps.
            instrument: Instrument symbol.
            timeframe: Timeframe string.

        Returns:
            Chronological list of StructureEvent objects.
        """
        n = len(highs)
        if n < 2 * self.config.swing_lookback + 1:
            logger.debug(
                "insufficient_bars",
                instrument=instrument,
                timeframe=timeframe,
                bars=n,
                required=2 * self.config.swing_lookback + 1,
            )
            return []

        # Step 1: Detect swings
        swings = detect_swings(
            highs=highs,
            lows=lows,
            timestamps=timestamps,
            lookback=self.config.swing_lookback,
            confirmation_bars=self.config.swing_confirmation_bars,
            min_distance_bars=self.config.min_structure_distance_bars,
            min_swing_size_pct=self.config.min_swing_size_pct,
        )

        if not swings:
            return []

        # Step 2: Analyze structure
        events = analyze_structure(
            swings=swings,
            highs=highs,
            lows=lows,
            closes=closes,
            opens=opens,
            timestamps=timestamps,
            instrument=instrument,
            timeframe=timeframe,
            config=self.config.to_dict(),
        )

        logger.info(
            "structure_analysis_complete",
            instrument=instrument,
            timeframe=timeframe,
            bars=n,
            swings=len(swings),
            events=len(events),
        )

        return events

    def analyze_from_ohlcv(
        self,
        bars: list,
        instrument: str,
        timeframe: str,
    ) -> list[StructureEvent]:
        """Analyze structure from a list of OHLCVBar objects."""
        if not bars:
            return []

        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]
        opens = [b.open for b in bars]
        timestamps = [b.timestamp for b in bars]

        return self.analyze_bars(
            highs=highs, lows=lows, closes=closes, opens=opens,
            timestamps=timestamps, instrument=instrument, timeframe=timeframe,
        )
