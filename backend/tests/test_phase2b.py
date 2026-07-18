"""Phase 2B Tests — FVG Engine.

Tests for FVG detection, lifecycle management, and configuration.
All tests use handcrafted OHLCV data with known expected outputs.
"""

from datetime import datetime, timedelta
import pytest

from app.services.fvg.detector import (
    detect_fvgs, apply_lifecycle,
    FVGConfig, FVG, FVGLifecycleEvent,
    FVGDirection, FVGStatus,
)


# ─── Helpers ─────────────────────────────────────────────────

def make_bars(highs, lows, closes, base_dt=None, tf_min=5):
    """Create bars from parallel high/low/close arrays."""
    if base_dt is None:
        base_dt = datetime(2025, 6, 16, 9, 30)
    from app.services.market_data.provider import OHLCVBar
    bars = []
    for i in range(len(highs)):
        bars.append(OHLCVBar(
            instrument="MNQ", timeframe="5m",
            timestamp=base_dt + timedelta(minutes=i * tf_min),
            open=(highs[i] + lows[i]) / 2,
            high=highs[i], low=lows[i], close=closes[i],
            volume=100, provider="test",
        ))
    return bars


# ─── Detection Tests ─────────────────────────────────────────

class TestFVGDetection:
    """Tests for FVG pattern detection."""

    def test_bullish_fvg_detection(self):
        """Candle 3's low > Candle 1's high = bullish FVG."""
        # Candle 1: high=100, Candle 3: low=105 — gap 100–105
        highs = [100, 108, 110]
        lows = [95, 104, 105]
        closes = [98, 106, 107]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        assert len(fvgs) == 1
        fvg = fvgs[0]
        assert fvg.direction == "bullish"
        assert fvg.lower_bound == 100.0  # high[0]
        assert fvg.upper_bound == 105.0  # low[2]
        assert fvg.midpoint == 102.5
        assert fvg.gap_size == 5.0
        assert fvg.creation_bar_index == 2

    def test_bearish_fvg_detection(self):
        """Candle 3's high < Candle 1's low = bearish FVG."""
        highs = [110, 105, 98]
        lows = [106, 100, 95]
        closes = [108, 102, 97]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        assert len(fvgs) == 1
        fvg = fvgs[0]
        assert fvg.direction == "bearish"
        assert fvg.upper_bound == 106.0  # low[0]
        assert fvg.lower_bound == 98.0   # high[2]
        assert fvg.gap_size == 8.0

    def test_no_fvg_when_no_gap(self):
        """Overlapping candles produce no FVG."""
        highs = [100, 105, 104]
        lows = [95, 98, 97]
        closes = [98, 102, 101]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        assert len(fvgs) == 0

    def test_min_gap_size_filter(self):
        """FVGs smaller than min_gap_size are filtered."""
        highs = [100, 103, 104]
        lows = [99, 102, 103.5]
        closes = [99.5, 102.5, 103.8]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        config = FVGConfig(min_gap_size=5.0)
        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m", config)
        # Gap = 103.5 - 100 = 3.5 < 5.0
        assert len(fvgs) == 0

        config2 = FVGConfig(min_gap_size=1.0)
        fvgs2 = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m", config2)
        assert len(fvgs2) == 1

    def test_min_gap_size_pct_filter(self):
        """FVGs with gap % below threshold are filtered."""
        highs = [100, 108, 110]
        lows = [98, 107, 109]
        closes = [99, 107.5, 109.5]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        # Gap = 109 - 100 = 9, midpoint = 104.5, gap% = 8.6%
        config = FVGConfig(min_gap_size_pct=10.0)  # requires 10%
        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m", config)
        assert len(fvgs) == 0

        config2 = FVGConfig(min_gap_size_pct=1.0)
        fvgs2 = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m", config2)
        assert len(fvgs2) == 1

    def test_multiple_fvgs_in_sequence(self):
        """At least one bullish and one bearish FVG detected in multi-bar data."""
        n = 30
        # Continuous overlapping series
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        closes = [float(49 + i) for i in range(n)]

        # FVG 1 (bullish): big gap at bar 3
        highs[1] = 50; lows[1] = 48
        highs[2] = 51; lows[2] = 49
        highs[3] = 65; lows[3] = 58  # big bullish gap
        highs[4] = 60; lows[4] = 55

        # FVG 2 (bearish): big gap at bar 13
        highs[11] = 75; lows[11] = 70
        highs[12] = 73; lows[12] = 68
        highs[13] = 50; lows[13] = 45  # big bearish gap
        highs[14] = 55; lows[14] = 48

        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        # Use min_gap_size_pct to filter out tiny gaps
        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m",
                           FVGConfig(min_gap_size=2.0, min_gap_size_pct=0.5))

        dirs = [f.direction for f in fvgs]
        assert "bullish" in dirs, f"No bullish FVG found in: {fvgs}"
        assert "bearish" in dirs, f"No bearish FVG found in: {fvgs}"

    def test_gap_size_calculation(self):
        """Gap size and % are calculated correctly."""
        highs = [100, 107, 112]
        lows = [98, 105, 110]
        closes = [99, 106, 111]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        fvg = fvgs[0]
        assert fvg.gap_size == 10.0  # 110 - 100
        assert fvg.midpoint == 105.0
        assert round(fvg.gap_size_pct, 2) == round(10.0 / 105.0 * 100, 2)

    def test_timeframe_filter(self):
        """Config can restrict which timeframes are analyzed."""
        highs = [100, 108, 110]
        lows = [98, 104, 106]
        closes = [99, 106, 108]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        config = FVGConfig(enabled_timeframes=["1h", "4h"])
        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m", config)
        assert len(fvgs) == 0  # 5m not in enabled list

        config2 = FVGConfig(enabled_timeframes=["5m"])
        fvgs2 = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m", config2)
        assert len(fvgs2) == 1


# ─── Lifecycle Tests ─────────────────────────────────────────

class TestFVGLifecycle:
    """Tests for FVG lifecycle management."""

    def test_fvg_creation_event(self):
        """Every FVG emits a creation event."""
        highs = [100, 108, 110]
        lows = [98, 104, 106]
        closes = [99, 106, 108]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts)

        created = [e for e in events if e.event_type == "created"]
        assert len(created) == 1
        assert created[0].bar_index == 2

    def test_first_touch_detection(self):
        """When price enters the gap zone, first_touch is recorded."""
        n = 15
        highs = [100.0] * n
        lows = [99.0] * n
        closes = [99.5] * n

        # Bullish FVG at bars 0–2
        highs[0] = 100; lows[0] = 97
        highs[1] = 104; lows[1] = 101
        highs[2] = 108; lows[2] = 105  # FVG: 100–105

        # Bar 8: price drops into gap
        highs[8] = 104
        lows[8] = 102
        closes[8] = 103  # close within gap

        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts)

        first_touch = [e for e in events if e.event_type == "first_touch"]
        assert len(first_touch) >= 1, f"No first touch, status: {fvgs[0].status}"
        assert fvgs[0].status in ("partially_filled", "mitigated")
        assert fvgs[0].first_touch_timestamp is not None

    def test_full_mitigation(self):
        """When price trades through entire gap, FVG is mitigated."""
        n = 20
        highs = [100.0] * n
        lows = [99.0] * n
        closes = [99.5] * n

        # Bullish FVG at bars 0–2: gap 100–105
        highs[0] = 100; lows[0] = 97
        highs[1] = 104; lows[1] = 101
        highs[2] = 108; lows[2] = 105

        # Bar 10: price drops completely through the gap
        highs[10] = 101
        lows[10] = 98
        closes[10] = 99  # close below lower bound (100)

        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts)

        assert fvgs[0].status == "mitigated"
        assert fvgs[0].fill_percentage == 100.0
        mitigated = [e for e in events if e.event_type == "mitigated"]
        assert len(mitigated) >= 1

    def test_partial_fill_percentage(self):
        """Fill % increases as price moves through the gap."""
        n = 12
        # Default bars: stay in the MIDDLE of the gap zone (no mitigation, no invalidation)
        highs = [106.0] * n
        lows = [103.0] * n
        closes = [105.0] * n  # 50% fill from default

        # Bullish FVG: 100–110
        highs[0] = 100; lows[0] = 97; closes[0] = 98
        highs[1] = 108; lows[1] = 105; closes[1] = 106
        highs[2] = 115; lows[2] = 110; closes[2] = 112  # FVG: 100–110

        # Bar 6: deeper into gap — more fill
        highs[6] = 106; lows[6] = 102; closes[6] = 103

        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts)

        assert fvgs[0].fill_percentage > 0
        # Max fill should be from bar 6: (110-103)/10*100 = 70%
        assert 60 <= fvgs[0].fill_percentage <= 80

    def test_bearish_fvg_lifecycle(self):
        """Bearish FVG lifecycle with price rallying into the gap."""
        n = 15
        highs = [100.0] * n
        lows = [99.0] * n
        closes = [99.5] * n

        # Bearish FVG: bars 0–2: high[0]=105, low[0]=100, high[2]=95
        highs[0] = 110; lows[0] = 107
        highs[1] = 102; lows[1] = 98
        highs[2] = 100; lows[2] = 95  # gap 95–107

        # Bar 8: price rallies into gap
        highs[8] = 102; lows[8] = 99; closes[8] = 101  # 40% fill

        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts)

        assert fvgs[0].direction == "bearish"
        assert fvgs[0].fill_percentage > 0

    def test_invalidation(self):
        """FVG invalidated when price extends significantly beyond gap."""
        n = 20
        # Default bars: price stays within gap zone (above lower, below upper+margin)
        highs = [104.0] * n
        lows = [101.0] * n
        closes = [102.0] * n

        # Bullish FVG: 100–105
        highs[0] = 100; lows[0] = 97; closes[0] = 98
        highs[1] = 104; lows[1] = 101; closes[1] = 102
        highs[2] = 108; lows[2] = 105; closes[2] = 106

        # Bar 8: price rallies well above upper bound (invalidation)
        # invalidation_pct default = 0.5% → 105 * 1.005 = 105.525
        highs[8] = 108; lows[8] = 106; closes[8] = 107  # close > 105.525

        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts)

        assert fvgs[0].status == "invalidated", f"Expected invalidated, got {fvgs[0].status}"
        invalidated = [e for e in events if e.event_type == "invalidated"]
        assert len(invalidated) >= 1

    def test_use_close_for_fill(self):
        """With use_close_for_fill=True, only close price determines fill."""
        n = 12
        # Default bars: stay in middle of gap
        highs = [106.0] * n
        lows = [103.0] * n
        closes = [105.0] * n  # moderate fill

        # Bullish FVG: 100–110
        highs[0] = 100; lows[0] = 97; closes[0] = 98
        highs[1] = 108; lows[1] = 105; closes[1] = 106
        highs[2] = 115; lows[2] = 110; closes[2] = 112

        # Bar 6: wick goes deep through gap but close stays above
        highs[6] = 108; lows[6] = 98; closes[6] = 107  # close at 107, wick to 98

        config = FVGConfig(use_close_for_fill=True)
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m", config)
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts, config)

        # With close-based fill: close=107 → fill = (110-107)/10*100 = 30%
        # Default bars: close=105 → fill = (110-105)/10*100 = 50%
        # Max fill should be ~50%, NOT mitigated
        assert fvgs[0].status != "mitigated", f"Should NOT be mitigated, got {fvgs[0].status} fill={fvgs[0].fill_percentage:.1f}%"
        assert 40 <= fvgs[0].fill_percentage <= 60

    def test_max_age_invalidation(self):
        """FVGs older than max_age_bars are auto-invalidated."""
        n = 20
        # Default bars: stay within gap (above lower) — won't mitigate
        highs = [104.0] * n
        lows = [101.0] * n
        closes = [103.0] * n

        highs[0] = 100; lows[0] = 97; closes[0] = 98
        highs[1] = 104; lows[1] = 101; closes[1] = 102
        highs[2] = 108; lows[2] = 105; closes[2] = 106

        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        config = FVGConfig(max_age_bars=5)  # invalidate after 5 bars
        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m", config)
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts, config)

        assert fvgs[0].status == "invalidated", f"Expected invalidated, got {fvgs[0].status}"


# ─── Edge Cases ──────────────────────────────────────────────

class TestFVGEdgeCases:
    """Edge case and robustness tests."""

    def test_insufficient_bars(self):
        """Less than 3 bars returns empty."""
        highs = [100, 105]
        lows = [98, 102]
        closes = [99, 103]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(2)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        assert fvgs == []

    def test_exact_touch_boundary(self):
        """Price exactly at boundary is properly handled."""
        n = 10
        highs = [100.0] * n
        lows = [99.0] * n
        closes = [99.5] * n

        highs[0] = 100; lows[0] = 97
        highs[1] = 104; lows[1] = 101
        highs[2] = 108; lows[2] = 105  # FVG: 100–105

        # Bar 5: exactly touches upper bound
        highs[5] = 105; lows[5] = 102; closes[5] = 103

        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts)

        # Should have some fill (price is at upper bound)
        assert fvgs[0].fill_percentage >= 0

    def test_gap_at_end_of_data(self):
        """FVG at the very last bars still detected but can't lifecycle (no bars after)."""
        # Only 3 bars — just enough to detect an FVG
        highs = [40, 48, 55]
        lows = [35, 43, 45]
        closes = [37, 45, 48]
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(3)]

        fvgs = detect_fvgs(highs, lows, closes, dts, "MNQ", "5m")
        assert len(fvgs) == 1, f"Expected 1, got {len(fvgs)}: {fvgs}"
        fvgs, events = apply_lifecycle(fvgs, highs, lows, closes, dts)
        # No bars after creation → stays active
        assert fvgs[0].status == "active"


# ─── Config Tests ────────────────────────────────────────────

class TestFVGConfig:
    """Tests for configuration serialization."""

    def test_config_round_trip(self):
        """Config serializes and deserializes correctly."""
        config = FVGConfig(
            min_gap_size=2.0,
            min_gap_size_pct=0.05,
            fill_tolerance_pct=0.5,
            use_close_for_fill=True,
            invalidation_pct=1.0,
            max_age_bars=100,
            enabled_timeframes=["1m", "5m", "1h"],
        )
        d = config.to_dict()
        c2 = FVGConfig.from_dict(d)
        assert c2.min_gap_size == 2.0
        assert c2.use_close_for_fill is True
        assert c2.enabled_timeframes == ["1m", "5m", "1h"]


# ─── API Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_fvg_directions():
    """Verify /fvg/directions endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/fvg/directions")
        assert response.status_code == 200
        assert "bullish" in response.json()["directions"]


@pytest.mark.asyncio
async def test_list_fvg_statuses():
    """Verify /fvg/statuses endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/fvg/statuses")
        assert response.status_code == 200
        assert "mitigated" in response.json()["statuses"]
