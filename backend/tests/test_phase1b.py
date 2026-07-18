"""Phase 1B Tests — Market Structure Engine.

All tests use handcrafted OHLCV bar sequences.
Every expected output is explicitly asserted — no visual inspection.
"""

from datetime import datetime, timedelta
import pytest

from app.services.market_structure.config import MarketStructureConfig
from app.services.market_structure.swing_detector import detect_swings, SwingPoint
from app.services.market_structure.structure_analyzer import (
    analyze_structure,
    StructureEvent,
    StructureEventType,
)
from app.services.market_structure.engine import MarketStructureEngine


# ─── Helpers ─────────────────────────────────────────────────

def make_bar(
    dt: datetime, o: float, h: float, l: float, c: float, instrument="MNQ", tf="5m",
):
    """Create a minimal bar-like object for testing."""
    from app.services.market_data.provider import OHLCVBar
    return OHLCVBar(
        instrument=instrument, timeframe=tf, timestamp=dt,
        open=o, high=h, low=l, close=c, volume=100, provider="test",
    )


def make_bars(prices: list[tuple[float, float, float, float]], base_dt=None, tf_min=5):
    """Create bars from (open, high, low, close) tuples."""
    if base_dt is None:
        base_dt = datetime(2025, 6, 1, 9, 30)
    bars = []
    for i, (o, h, l, c) in enumerate(prices):
        bars.append(make_bar(base_dt + timedelta(minutes=i * tf_min), o, h, l, c))
    return bars


# ─── Swing Detection Tests ───────────────────────────────────

class TestSwingDetection:
    """Tests for the swing point detector."""

    def test_simple_swing_high(self):
        """A clear swing high in the middle of a sequence."""
        # Bar 5 has highest high in [0..10]
        prices = [
            (10, 12, 9, 11),
            (11, 13, 10, 12),
            (12, 14, 11, 13),
            (13, 15, 12, 14),
            (14, 16, 13, 15),
            (15, 20, 14, 16),  # ← Swing high at index 5
            (16, 17, 13, 14),
            (15, 16, 12, 13),
            (14, 15, 11, 12),
            (13, 14, 10, 11),
            (12, 13, 9, 10),
            (11, 12, 8, 9),
        ]
        highs = [h for _, h, _, _ in prices]
        lows = [lo for _, _, lo, _ in prices]
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(len(prices))]

        swings = detect_swings(highs, lows, dts, lookback=5, confirmation_bars=0, min_distance_bars=0)

        swing_highs = [s for s in swings if s.swing_type == "high"]
        assert len(swing_highs) == 1
        assert swing_highs[0].bar_index == 5
        assert swing_highs[0].price == 20.0

    def test_simple_swing_low(self):
        """A clear swing low."""
        prices = [
            (10, 11, 9, 10),
            (11, 12, 10, 11),
            (12, 13, 11, 12),
            (13, 14, 12, 13),
            (14, 15, 13, 14),
            (15, 16, 5, 14),   # ← Swing low at index 5 (low=5)
            (14, 15, 12, 13),
            (13, 14, 11, 12),
            (12, 13, 10, 11),
            (11, 12, 9, 10),
            (10, 11, 8, 9),
            (9, 10, 7, 8),
        ]
        highs = [h for _, h, _, _ in prices]
        lows = [lo for _, _, lo, _ in prices]
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(len(prices))]

        swings = detect_swings(highs, lows, dts, lookback=5, confirmation_bars=0, min_distance_bars=0)

        swing_lows = [s for s in swings if s.swing_type == "low"]
        assert len(swing_lows) == 1
        assert swing_lows[0].bar_index == 5
        assert swing_lows[0].price == 5.0

    def test_multiple_swings(self):
        """Detect multiple swing highs and lows in a sequence."""
        # Pattern: high at 5, low at 15, high at 25, low at 35
        n = 45
        highs = [10.0] * n
        lows = [9.0] * n
        highs[5] = 20.0   # swing high
        lows[15] = 2.0    # swing low
        highs[25] = 18.0  # swing high
        lows[35] = 3.0    # swing low
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        swings = detect_swings(highs, lows, dts, lookback=2, confirmation_bars=0, min_distance_bars=0)

        highs_list = [s for s in swings if s.swing_type == "high"]
        lows_list = [s for s in swings if s.swing_type == "low"]
        assert len(highs_list) == 2
        assert len(lows_list) == 2

    def test_min_distance_filter(self):
        """Swing points closer than min_distance are filtered."""
        n = 45
        highs = [10.0] * n
        lows = [9.0] * n
        highs[5] = 20.0   # first swing high
        highs[10] = 19.0  # too close (5 bars away, min_distance=6)
        highs[20] = 18.0  # far enough
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        swings = detect_swings(highs, lows, dts, lookback=2, confirmation_bars=0, min_distance_bars=6)

        highs_list = [s for s in swings if s.swing_type == "high"]
        assert len(highs_list) == 2  # index 5 and 20, not 10

    def test_confirmation_bars_delay(self):
        """With confirmation_bars=3, swings at the very end are not confirmed."""
        n = 20
        highs = [10.0] * n
        lows = [9.0] * n
        highs[5] = 20.0    # confirmed (5 + 3 < 20)
        highs[18] = 19.0   # NOT confirmed (18 + 3 = 21 > 20)
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        swings = detect_swings(highs, lows, dts, lookback=2, confirmation_bars=3, min_distance_bars=0)

        confirmed = [s for s in swings if s.confirmed]
        assert len(confirmed) == 1
        assert confirmed[0].bar_index == 5

    def test_edge_not_enough_bars(self):
        """Too few bars returns empty list."""
        highs = [10.0, 11.0, 10.0]
        lows = [9.0, 9.0, 9.0]
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        swings = detect_swings(highs, lows, dts, lookback=5)
        assert swings == []

    def test_flat_market_no_swings(self):
        """A completely flat price series should produce no swings."""
        n = 30
        highs = [10.0] * n
        lows = [9.0] * n
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0)
        # No bar has strictly higher high than all neighbors
        assert len(swings) == 0


# ─── Structure Analysis Tests ────────────────────────────────

class TestStructureAnalysis:
    """Tests for HH, HL, LH, LL classification."""

    def test_higher_high_detection(self):
        """Two swing highs: second higher than first = HH."""
        n = 50
        highs = [10.0] * n
        lows = [9.0] * n
        closes = [9.5] * n
        opens = [9.5] * n
        highs[10] = 20.0   # first swing high
        highs[30] = 25.0   # second swing high (higher)
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        swings = detect_swings(highs, lows, dts, lookback=3)
        events = analyze_structure(swings, highs, lows, closes, opens, dts, "MNQ", "5m")

        hh_events = [e for e in events if e.event_type == StructureEventType.HIGHER_HIGH]
        assert len(hh_events) == 1
        assert hh_events[0].price_level == 25.0

    def test_lower_high_detection(self):
        """Second swing high lower than first = LH."""
        n = 50
        highs = [10.0] * n
        lows = [9.0] * n
        closes = [9.5] * n
        opens = [9.5] * n
        highs[10] = 20.0   # first swing high
        highs[30] = 15.0   # second swing high (lower)
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        swings = detect_swings(highs, lows, dts, lookback=3)
        events = analyze_structure(swings, highs, lows, closes, opens, dts, "MNQ", "5m")

        lh_events = [e for e in events if e.event_type == StructureEventType.LOWER_HIGH]
        assert len(lh_events) == 1
        assert lh_events[0].price_level == 15.0

    def test_higher_low_detection(self):
        """Second swing low higher than first = HL."""
        n = 50
        highs = [10.0] * n
        lows = [9.0] * n
        closes = [9.5] * n
        opens = [9.5] * n
        lows[15] = 4.0    # first swing low
        lows[35] = 6.0    # second swing low (higher)
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        swings = detect_swings(highs, lows, dts, lookback=3)
        events = analyze_structure(swings, highs, lows, closes, opens, dts, "MNQ", "5m")

        hl_events = [e for e in events if e.event_type == StructureEventType.HIGHER_LOW]
        assert len(hl_events) == 1
        assert hl_events[0].price_level == 6.0

    def test_lower_low_detection(self):
        """Second swing low lower than first = LL."""
        n = 50
        highs = [10.0] * n
        lows = [9.0] * n
        closes = [9.5] * n
        opens = [9.5] * n
        lows[15] = 4.0    # first swing low
        lows[35] = 2.0    # second swing low (lower)
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        swings = detect_swings(highs, lows, dts, lookback=3)
        events = analyze_structure(swings, highs, lows, closes, opens, dts, "MNQ", "5m")

        ll_events = [e for e in events if e.event_type == StructureEventType.LOWER_LOW]
        assert len(ll_events) == 1
        assert ll_events[0].price_level == 2.0

    def test_first_swing_is_swing_not_hh_or_lh(self):
        """The first swing high should be classified as SWING_HIGH, not HH/LH."""
        n = 40
        highs = [10.0] * n
        lows = [9.0] * n
        closes = [9.5] * n
        opens = [9.5] * n
        highs[10] = 20.0
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        swings = detect_swings(highs, lows, dts, lookback=3)
        events = analyze_structure(swings, highs, lows, closes, opens, dts, "MNQ", "5m")

        first_high = [e for e in events if e.event_type == StructureEventType.SWING_HIGH]
        assert len(first_high) == 1
        assert first_high[0].price_level == 20.0


# ─── BOS/CHoCH/MSS Tests ────────────────────────────────────

class TestBOSChoCHMSS:
    """Tests for Break of Structure, Change of Character, MSS."""

    def _make_zigzag(self, n: int, lookback: int, peaks: list[tuple[int, float]],
                     valleys: list[tuple[int, float]]) -> tuple:
        """Build a zigzag price series with explicit peaks and valleys.
        
        Returns (highs, lows, closes, opens, dts).
        Background price is 50.0. Peaks set high to given value and lows to
        peak-2. Valleys set low to given value and highs to valley+2.
        """
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        # Set peaks: make bar i clearly higher than all neighbors
        for idx, price in peaks:
            for offset in range(-lookback, lookback + 1):
                j = idx + offset
                if 0 <= j < n and j != idx:
                    highs[j] = price - 5.0  # neighbors are much lower
                    lows[j] = price - 7.0
            highs[idx] = price
            lows[idx] = price - 2.0
            closes[idx] = price - 1.0
            opens[idx] = price - 1.5

        # Set valleys: make bar i clearly lower than all neighbors
        for idx, price in valleys:
            for offset in range(-lookback, lookback + 1):
                j = idx + offset
                if 0 <= j < n and j != idx:
                    highs[j] = price + 7.0  # neighbors are much higher
                    lows[j] = price + 5.0
            highs[idx] = price + 2.0
            lows[idx] = price
            closes[idx] = price + 1.0
            opens[idx] = price + 1.5

        return highs, lows, closes, opens, dts

    def test_bullish_bos(self):
        """In an uptrend, breaking above a prior swing high = BOS."""
        n = 100
        highs, lows, closes, opens, dts = self._make_zigzag(
            n, lookback=3,
            peaks=[(15, 65.0), (55, 72.0)],   # HH
            valleys=[(35, 55.0), (75, 58.0)],  # HL
        )
        # Break above first swing high (65.0) at bar 85
        highs[85] = 75.0
        closes[85] = 74.0
        lows[85] = 70.0

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)
        events = analyze_structure(
            swings, highs, lows, closes, opens, dts, "MNQ", "5m",
            config={"bos_requires_close": True},
        )
        bos_events = [e for e in events if e.event_type == StructureEventType.BOS]
        assert len(bos_events) >= 1, f"Expected BOS, got events: {[e.event_type.value for e in events]}"
        assert bos_events[0].direction == "bullish"

    def test_bearish_choch(self):
        """In a downtrend, breaking above a prior swing high = bullish CHoCH."""
        n = 100
        highs, lows, closes, opens, dts = self._make_zigzag(
            n, lookback=3,
            peaks=[(15, 65.0), (55, 60.0)],   # LH — downtrend
            valleys=[(35, 55.0), (75, 50.0)],  # LL — downtrend
        )
        # Break above first swing high (65.0) — CHoCH in downtrend
        highs[85] = 70.0
        closes[85] = 68.0
        lows[85] = 66.0

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)
        events = analyze_structure(
            swings, highs, lows, closes, opens, dts, "MNQ", "5m",
            config={"choch_requires_close": True},
        )
        choch_events = [e for e in events if e.event_type == StructureEventType.CHOCH]
        mss_events = [e for e in events if e.event_type == StructureEventType.MSS]
        # Should be either CHoCH or MSS
        found = choch_events + mss_events
        assert len(found) >= 1, f"Expected CHoCH/MSS, got events: {[e.event_type.value for e in events]}"
        assert found[0].direction == "bullish"

    def test_mss_on_close_confirmation(self):
        """MSS detected when CHoCH has close confirmation."""
        n = 100
        highs, lows, closes, opens, dts = self._make_zigzag(
            n, lookback=3,
            peaks=[(15, 65.0), (55, 60.0)],   # LH — downtrend
            valleys=[(35, 55.0), (75, 50.0)],  # LL — downtrend
        )
        # Break above first swing high with close well above
        highs[85] = 72.0
        closes[85] = 70.0  # close above 65.0
        lows[85] = 68.0

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)
        events = analyze_structure(
            swings, highs, lows, closes, opens, dts, "MNQ", "5m",
            config={"choch_requires_close": True},
        )
        mss_events = [e for e in events if e.event_type == StructureEventType.MSS]
        assert len(mss_events) >= 1, f"Expected MSS, got: {[e.event_type.value for e in events]}"
        assert mss_events[0].direction == "bullish"


# ─── Engine Tests ────────────────────────────────────────────

class TestMarketStructureEngine:
    """Integration tests for the full engine."""

    def test_analyze_bars_uptrend(self):
        """Full analysis of a clear uptrend sequence."""
        n = 100
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        lookback = 3
        # Peak 1 at bar 15
        for offset in range(-lookback, lookback + 1):
            j = 15 + offset
            if 0 <= j < n and j != 15:
                highs[j] = 65.0 - 5.0; lows[j] = 65.0 - 7.0
        highs[15] = 65.0; lows[15] = 63.0; closes[15] = 64.0; opens[15] = 63.5

        # Valley 1 at bar 35
        for offset in range(-lookback, lookback + 1):
            j = 35 + offset
            if 0 <= j < n and j != 35:
                highs[j] = 55.0 + 7.0; lows[j] = 55.0 + 5.0
        highs[35] = 57.0; lows[35] = 55.0; closes[35] = 56.0; opens[35] = 56.5

        # Peak 2 (HH) at bar 55
        for offset in range(-lookback, lookback + 1):
            j = 55 + offset
            if 0 <= j < n and j != 55:
                highs[j] = 72.0 - 5.0; lows[j] = 72.0 - 7.0
        highs[55] = 72.0; lows[55] = 70.0; closes[55] = 71.0; opens[55] = 70.5

        # Valley 2 (HL) at bar 75
        for offset in range(-lookback, lookback + 1):
            j = 75 + offset
            if 0 <= j < n and j != 75:
                highs[j] = 58.0 + 7.0; lows[j] = 58.0 + 5.0
        highs[75] = 60.0; lows[75] = 58.0; closes[75] = 59.0; opens[75] = 59.5

        engine = MarketStructureEngine(MarketStructureConfig(
            swing_lookback=3,
            swing_confirmation_bars=0,
            min_structure_distance_bars=2,
        ))

        events = engine.analyze_bars(highs, lows, closes, opens, dts, "MNQ", "5m")

        event_types = [e.event_type for e in events]
        assert StructureEventType.SWING_HIGH in event_types
        assert StructureEventType.HIGHER_LOW in event_types
        assert StructureEventType.HIGHER_HIGH in event_types

    def test_insufficient_bars_returns_empty(self):
        """Too few bars returns empty list."""
        engine = MarketStructureEngine(MarketStructureConfig(swing_lookback=5))
        events = engine.analyze_bars(
            [10.0, 11.0, 10.0],
            [9.0, 9.0, 9.0],
            [9.5, 10.5, 9.5],
            [9.5, 10.5, 9.5],
            [datetime(2025, 6, 1, 9, 30) + timedelta(minutes=i * 5) for i in range(3)],
            "MNQ", "5m",
        )
        assert events == []

    def test_config_serialization(self):
        """Config to_dict is serializable."""
        config = MarketStructureConfig(
            swing_lookback=7,
            bos_requires_close=False,
        )
        d = config.to_dict()
        assert d["swing_lookback"] == 7
        assert d["bos_requires_close"] is False

        # Round trip
        c2 = MarketStructureConfig.from_dict(d)
        assert c2.swing_lookback == 7
        assert c2.bos_requires_close is False

    def test_analyze_from_ohlcv(self):
        """Engine works with OHLCVBar objects."""
        bars = []
        base = datetime(2025, 6, 1, 9, 30)
        for i in range(50):
            h = 10.0
            lo = 9.0
            if i == 15:
                h = 20.0  # swing high
            bars.append(make_bar(
                base + timedelta(minutes=i * 5), 9.5, h, lo, 9.5,
            ))

        engine = MarketStructureEngine(MarketStructureConfig(swing_lookback=3))
        events = engine.analyze_from_ohlcv(bars, "MNQ", "5m")
        assert len(events) > 0
        assert events[0].instrument == "MNQ"


# ─── API Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_event_types():
    """Verify /market-structure/event-types returns all types."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/market-structure/event-types")
        assert response.status_code == 200
        data = response.json()
        types = data["event_types"]
        assert "swing_high" in types
        assert "bos" in types
        assert "choch" in types
        assert "mss" in types
        assert "higher_high" in types
        assert "lower_low" in types
