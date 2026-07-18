"""Phase 2A Tests — Liquidity Engine.

Tests for session engine, liquidity level detection, and liquidity events.
All tests use handcrafted OHLCV data with known expected outputs.
"""

from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import pytest

from app.services.liquidity.session_engine import (
    SessionEngine, SessionConfig, SessionName, SessionBoundary,
    DEFAULT_SESSION_TIMES,
)
from app.services.liquidity.engine import (
    LiquidityEngine, LiquidityConfig,
    LiquidityLevel, LiquidityEvent,
    LiquidityType, LiquidityEventType,
)
from app.services.market_structure.swing_detector import detect_swings, SwingPoint


# ─── Helpers ─────────────────────────────────────────────────

def make_bars(prices: list[tuple[float, float, float, float]], base_dt=None, tf_min=5):
    """Create bars from (open, high, low, close) tuples."""
    if base_dt is None:
        base_dt = datetime(2025, 6, 15, 18, 0)  # Sunday evening ET (Asia session)
    from app.services.market_data.provider import OHLCVBar
    bars = []
    for i, (o, h, l, c) in enumerate(prices):
        bars.append(OHLCVBar(
            instrument="MNQ", timeframe="5m",
            timestamp=base_dt + timedelta(minutes=i * tf_min),
            open=o, high=h, low=l, close=c, volume=100, provider="test",
        ))
    return bars


# ─── Session Engine Tests ────────────────────────────────────

class TestSessionEngine:
    """Tests for session boundaries and timezone handling."""

    def test_session_detection_ny_am(self):
        """A bar during NY AM (9:30-12:00 ET) should be detected."""
        engine = SessionEngine()
        dt = datetime(2025, 6, 16, 14, 0, tzinfo=ZoneInfo("UTC"))  # 10:00 ET
        session = engine.get_session(dt)
        assert session == SessionName.NY_AM

    def test_session_detection_london(self):
        """A bar during London session should be detected."""
        engine = SessionEngine()
        dt = datetime(2025, 6, 16, 7, 0, tzinfo=ZoneInfo("UTC"))  # 3:00 ET = 8:00 GMT
        session = engine.get_session(dt)
        assert session == SessionName.LONDON

    def test_session_detection_asia(self):
        """A bar during Asia session should be detected."""
        engine = SessionEngine()
        dt = datetime(2025, 6, 16, 1, 0, tzinfo=ZoneInfo("UTC"))  # 21:00 ET
        session = engine.get_session(dt)
        assert session == SessionName.ASIA

    def test_between_sessions_returns_none(self):
        """Between NY PM close and Asia open, no session active."""
        engine = SessionEngine()
        dt = datetime(2025, 6, 16, 21, 0, tzinfo=ZoneInfo("UTC"))  # 17:00 ET
        session = engine.get_session(dt)
        assert session is None

    def test_session_boundary_computation(self):
        """Session boundaries are computed correctly."""
        engine = SessionEngine()
        ref = datetime(2025, 6, 16, 14, 0, tzinfo=ZoneInfo("UTC"))  # 10:00 ET

        boundary = engine.compute_session_boundary(SessionName.NY_AM, ref)

        # NY AM starts at 9:30 ET = 13:30 UTC (June)
        # NY AM ends at 12:00 ET = 16:00 UTC
        assert boundary.start_utc.hour == 13
        assert boundary.start_utc.minute == 30
        assert boundary.end_utc.hour == 16
        assert boundary.end_utc.minute == 0

    def test_overnight_session_boundary(self):
        """Asia session (overnight 20:00-02:00 ET) handles date wrap."""
        engine = SessionEngine()
        ref = datetime(2025, 6, 16, 1, 0, tzinfo=ZoneInfo("UTC"))

        boundary = engine.compute_session_boundary(SessionName.ASIA, ref)

        assert boundary.session == SessionName.ASIA
        # End should be after start for overnight
        assert boundary.end_utc > boundary.start_utc

    def test_custom_timezone(self):
        """Session engine works with a non-ET timezone."""
        config = SessionConfig(timezone="Europe/London")
        engine = SessionEngine(config)
        dt = datetime(2025, 6, 16, 13, 30, tzinfo=ZoneInfo("UTC"))  # 14:30 BST
        session = engine.get_session(dt)
        # With London timezone, default session times would map differently
        assert session is not None  # Should still resolve

    def test_config_serialization(self):
        """SessionConfig round-trips through dict."""
        config = SessionConfig(
            timezone="Asia/Tokyo",
            session_times={
                SessionName.ASIA: (time(9, 0), time(15, 0)),
            },
        )
        d = config.to_dict()
        c2 = SessionConfig.from_dict(d)
        assert c2.timezone == "Asia/Tokyo"
        assert c2.session_times[SessionName.ASIA] == (time(9, 0), time(15, 0))


# ─── Liquidity Level Detection Tests ─────────────────────────

class TestLiquidityLevels:
    """Tests for level detection: PDH/PDL, sessions, equal highs/lows."""

    def test_pdh_pdl_detection(self):
        """Previous day high/low detected from prior day's bars."""
        # Start Monday evening, create bars spanning Monday and Tuesday
        base = datetime(2025, 6, 16, 22, 0)  # Monday 22:00 UTC = 18:00 ET
        n = 48  # 4 hours at 5min = 48 bars: 24 Mon, 24 Tue
        bars = []
        for i in range(n):
            ts = base + timedelta(minutes=i * 5)
            if i < 24:
                # Monday bars: high ranges 105-109, low ranges 98-100
                o, h, l, c = 102.0, 105.0 + i * 0.15, 98.0 + i * 0.08, 101.0
            else:
                # Tuesday bars: higher
                o, h, l, c = 108.0, 113.0 + (i % 4), 107.0, 110.0
            from app.services.market_data.provider import OHLCVBar
            bars.append(OHLCVBar(
                instrument="MNQ", timeframe="5m",
                timestamp=ts, open=o, high=h, low=l, close=c,
                volume=100, provider="test",
            ))

        engine = LiquidityEngine()
        levels = engine.detect_levels(bars)

        pdh_levels = [l for l in levels if l.level_type == LiquidityType.PDH]
        pdl_levels = [l for l in levels if l.level_type == LiquidityType.PDL]

        assert len(pdh_levels) >= 1, f"PDH not detected, levels: {[l.level_type.value for l in levels]}"
        assert len(pdl_levels) >= 1, "PDL not detected"

    def test_session_levels_detected(self):
        """Session highs/lows are detected for bars within sessions."""
        bars = make_bars([
            # Overnight / Asia-ish bars
            (100, 102, 98, 101), (101, 104, 100, 103), (103, 105, 101, 102),
            (102, 103, 99, 100), (100, 101, 97, 99), (99, 102, 98, 101),
            (101, 106, 100, 105), (105, 107, 103, 104),
            # London session bars
            (104, 108, 103, 107), (107, 110, 106, 108), (108, 111, 105, 106),
            (106, 109, 104, 108), (108, 112, 107, 111), (111, 113, 109, 110),
            # NY AM bars
            (110, 114, 109, 113), (113, 116, 112, 114), (114, 117, 113, 115),
            (115, 118, 114, 116), (116, 119, 115, 117), (117, 120, 116, 118),
        ], base_dt=datetime(2025, 6, 16, 0, 0))  # midnight UTC = 20:00 ET (Asia)

        engine = LiquidityEngine()
        levels = engine.detect_levels(bars)

        session_types = [l.level_type for l in levels]
        # Should find at least one session level
        assert any("asia" in t.value for t in session_types) or \
               any("london" in t.value for t in session_types) or \
               any("ny" in t.value for t in session_types), \
               f"No session levels found in: {session_types}"

    def test_equal_highs_detection(self):
        """Two swing highs at near-identical prices = equal highs."""
        n = 80
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        # Peak 1 at bar 15
        for offset in range(-3, 4):
            j = 15 + offset
            if 0 <= j < n and j != 15:
                highs[j] = 65.0 - 5.0; lows[j] = 65.0 - 7.0
        highs[15] = 65.0; lows[15] = 63.0

        # Peak 2 at bar 45: same price level (within tolerance)
        for offset in range(-3, 4):
            j = 45 + offset
            if 0 <= j < n and j != 45:
                highs[j] = 65.03 - 5.0; lows[j] = 65.03 - 7.0
        highs[45] = 65.03; lows[45] = 63.03  # 0.046% difference

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)

        bars = make_bars([
            (o, h, lo, c) for o, h, lo, c in zip(opens, highs, lows, closes)
        ], base_dt=datetime(2025, 6, 16, 9, 30))

        engine = LiquidityEngine(LiquidityConfig(equal_level_tolerance_pct=0.05))
        levels = engine.detect_levels(bars, swings)

        eq_highs = [l for l in levels if l.level_type == LiquidityType.EQUAL_HIGHS]
        assert len(eq_highs) >= 1, f"Equal highs not detected, levels: {[l.level_type.value for l in levels]}"
        assert eq_highs[0].metadata["count"] >= 2

    def test_equal_lows_detection(self):
        """Two swing lows at near-identical prices = equal lows."""
        n = 80
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        # Valley 1 at bar 20
        for offset in range(-3, 4):
            j = 20 + offset
            if 0 <= j < n and j != 20:
                highs[j] = 45.0 + 7.0; lows[j] = 45.0 + 5.0
        highs[20] = 47.0; lows[20] = 45.0

        # Valley 2 at bar 55: same level
        for offset in range(-3, 4):
            j = 55 + offset
            if 0 <= j < n and j != 55:
                highs[j] = 45.02 + 7.0; lows[j] = 45.02 + 5.0
        highs[55] = 47.02; lows[55] = 45.02  # 0.044% diff

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)

        bars = make_bars([
            (o, h, lo, c) for o, h, lo, c in zip(opens, highs, lows, closes)
        ], base_dt=datetime(2025, 6, 16, 9, 30))

        engine = LiquidityEngine(LiquidityConfig(equal_level_tolerance_pct=0.05))
        levels = engine.detect_levels(bars, swings)

        eq_lows = [l for l in levels if l.level_type == LiquidityType.EQUAL_LOWS]
        assert len(eq_lows) >= 1, f"Equal lows not detected"
        assert eq_lows[0].metadata["count"] >= 2

    def test_swing_liquidity_detection(self):
        """Swing highs/lows generate liquidity levels."""
        n = 80
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        for offset in range(-3, 4):
            j = 20 + offset
            if 0 <= j < n and j != 20:
                highs[j] = 65.0 - 5.0; lows[j] = 65.0 - 7.0
        highs[20] = 65.0; lows[20] = 63.0

        for offset in range(-3, 4):
            j = 50 + offset
            if 0 <= j < n and j != 50:
                highs[j] = 55.0 + 7.0; lows[j] = 55.0 + 5.0
        highs[50] = 57.0; lows[50] = 55.0

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)
        bars = make_bars([
            (o, h, lo, c) for o, h, lo, c in zip(opens, highs, lows, closes)
        ], base_dt=datetime(2025, 6, 16, 9, 30))

        engine = LiquidityEngine()
        levels = engine.detect_levels(bars, swings)

        sh_liq = [l for l in levels if l.level_type == LiquidityType.SWING_HIGH_LIQ]
        sl_liq = [l for l in levels if l.level_type == LiquidityType.SWING_LOW_LIQ]

        assert len(sh_liq) >= 1, "Swing high liquidity not detected"
        assert len(sl_liq) >= 1, "Swing low liquidity not detected"


# ─── Liquidity Event Tests ───────────────────────────────────

class TestLiquidityEvents:
    """Tests for liquidity events: sweep, rejection, break, approach."""

    def test_sweep_detection(self):
        """Price wicks through a level then reverses = sweep."""
        n = 60
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        # Create a swing high at bar 15 → liquidity above
        for offset in range(-3, 4):
            j = 15 + offset
            if 0 <= j < n and j != 15:
                highs[j] = 65.0 - 5.0; lows[j] = 65.0 - 7.0
        highs[15] = 65.0; lows[15] = 63.0

        # Bar 40: price wicks above 65.0 but closes below
        highs[40] = 66.0
        lows[40] = 63.0
        opens[40] = 64.0
        closes[40] = 64.5  # close below 65.0

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)
        bars = make_bars([
            (o, h, lo, c) for o, h, lo, c in zip(opens, highs, lows, closes)
        ], base_dt=datetime(2025, 6, 16, 9, 30))

        engine = LiquidityEngine(LiquidityConfig(sweep_wick_pct=0.01))
        levels = engine.detect_levels(bars, swings)
        events = engine.detect_events(levels, bars)

        sweeps = [e for e in events if e.event_type == LiquidityEventType.SWEPT]
        assert len(sweeps) >= 1, f"Sweep not detected, events: {[e.event_type.value for e in events]}"

    def test_rejection_detection(self):
        """Price touches level with open above, closes well below = rejection."""
        n = 60
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        # Swing high at bar 15
        for offset in range(-3, 4):
            j = 15 + offset
            if 0 <= j < n and j != 15:
                highs[j] = 65.0 - 5.0; lows[j] = 65.0 - 7.0
        highs[15] = 65.0; lows[15] = 63.0

        # Bar 40: opens above, touches higher, closes well below — rejection
        highs[40] = 65.5   # wicks above 65.0
        lows[40] = 62.0
        opens[40] = 65.3   # open above level
        closes[40] = 63.0  # close well below (reversal ~3%)

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)
        bars = make_bars([
            (o, h, lo, c) for o, h, lo, c in zip(opens, highs, lows, closes)
        ], base_dt=datetime(2025, 6, 16, 9, 30))

        engine = LiquidityEngine(LiquidityConfig(rejection_reversal_pct=0.15))
        levels = engine.detect_levels(bars, swings)
        events = engine.detect_events(levels, bars)

        rejections = [e for e in events if e.event_type == LiquidityEventType.REJECTED]
        assert len(rejections) >= 1, f"Rejection not detected, events: {[e.event_type.value for e in events]}"

    def test_break_detection(self):
        """Price closes beyond a level = break."""
        n = 60
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        # Swing high at bar 15
        for offset in range(-3, 4):
            j = 15 + offset
            if 0 <= j < n and j != 15:
                highs[j] = 65.0 - 5.0; lows[j] = 65.0 - 7.0
        highs[15] = 65.0; lows[15] = 63.0

        # Bar 40: clean break above 65.0
        highs[40] = 67.0
        lows[40] = 65.5
        opens[40] = 66.0
        closes[40] = 66.5  # close + low both above 65.0

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)
        bars = make_bars([
            (o, h, lo, c) for o, h, lo, c in zip(opens, highs, lows, closes)
        ], base_dt=datetime(2025, 6, 16, 9, 30))

        engine = LiquidityEngine(LiquidityConfig(break_requires_close=True))
        levels = engine.detect_levels(bars, swings)
        events = engine.detect_events(levels, bars)

        breaks = [e for e in events if e.event_type == LiquidityEventType.BROKEN]
        assert len(breaks) >= 1, f"Break not detected, events: {[e.event_type.value for e in events]}"

    def test_approach_detection(self):
        """Price approaches within threshold of a level."""
        n = 60
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        # Swing high at bar 15
        for offset in range(-3, 4):
            j = 15 + offset
            if 0 <= j < n and j != 15:
                highs[j] = 65.0 - 5.0; lows[j] = 65.0 - 7.0
        highs[15] = 65.0; lows[15] = 63.0

        # Bar 40: approaches within 0.05% but doesn't touch
        highs[40] = 64.98   # 0.03% from 65.0
        lows[40] = 64.0
        opens[40] = 64.5
        closes[40] = 64.7

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)
        bars = make_bars([
            (o, h, lo, c) for o, h, lo, c in zip(opens, highs, lows, closes)
        ], base_dt=datetime(2025, 6, 16, 9, 30))

        engine = LiquidityEngine(LiquidityConfig(approach_threshold_pct=0.1))
        levels = engine.detect_levels(bars, swings)
        events = engine.detect_events(levels, bars)

        approaches = [e for e in events if e.event_type == LiquidityEventType.APPROACHED]
        assert len(approaches) >= 1, f"Approach not detected, events: {[e.event_type.value for e in events]}"


# ─── Integration Tests ──────────────────────────────────────

class TestLiquidityIntegration:
    """Full pipeline tests."""

    def test_full_detect_no_errors(self):
        """Full detection pipeline runs without errors."""
        n = 100
        highs = [50.0] * n
        lows = [48.0] * n
        closes = [49.0] * n
        opens = [49.0] * n
        dts = [datetime(2025, 6, 16, 9, 30) + timedelta(minutes=i * 5) for i in range(n)]

        for offset in range(-3, 4):
            j = 20 + offset
            if 0 <= j < n and j != 20:
                highs[j] = 65.0 - 5.0; lows[j] = 65.0 - 7.0
        highs[20] = 65.0; lows[20] = 63.0

        for offset in range(-3, 4):
            j = 50 + offset
            if 0 <= j < n and j != 50:
                highs[j] = 55.0 + 7.0; lows[j] = 55.0 + 5.0
        highs[50] = 57.0; lows[50] = 55.0

        # Break above swing high
        highs[80] = 67.0; lows[80] = 65.5; closes[80] = 66.5; opens[80] = 66.0

        swings = detect_swings(highs, lows, dts, lookback=3, confirmation_bars=0, min_distance_bars=2)
        bars = make_bars([
            (o, h, lo, c) for o, h, lo, c in zip(opens, highs, lows, closes)
        ], base_dt=datetime(2025, 6, 16, 9, 30))

        engine = LiquidityEngine()
        levels = engine.detect_levels(bars, swings)
        events = engine.detect_events(levels, bars)

        # Should always produce some output
        assert len(levels) > 0, "No levels detected"
        assert len(events) > 0, "No events detected"

    def test_level_type_coverage(self):
        """Verify all expected level types exist in enum."""
        expected = {
            "pdh", "pdl", "pwh", "pwl", "pmh", "pml",
            "asia_high", "asia_low", "london_high", "london_low",
            "ny_high", "ny_low", "equal_highs", "equal_lows",
            "swing_high_liq", "swing_low_liq", "internal_high", "internal_low",
        }
        actual = {e.value for e in LiquidityType}
        assert expected == actual, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_event_type_coverage(self):
        """Verify all expected event types exist in enum."""
        expected = {"approached", "touched", "swept", "rejected", "broken", "invalidated"}
        actual = {e.value for e in LiquidityEventType}
        assert expected == actual, f"Missing: {expected - actual}, Extra: {actual - expected}"


# ─── API Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_liquidity_event_types():
    """Verify /liquidity/event-types returns all types."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/liquidity/event-types")
        assert response.status_code == 200
        data = response.json()
        assert "pdh" in data["level_types"]
        assert "swept" in data["event_types"]


@pytest.mark.asyncio
async def test_session_history_endpoint():
    """Verify /liquidity/session-history returns session boundaries."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/liquidity/session-history?instrument=MNQ")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "asia" in data["sessions"]
        assert "london" in data["sessions"]
