"""Phase 2C Tests — Order Block Engine.

Tests for OB detection, BOS/CHoCH-triggered creation, lifecycle,
mitigation, invalidation, and related entity references.
"""

from datetime import datetime, timedelta
import pytest

from app.services.order_block.detector import (
    detect_order_blocks, apply_ob_lifecycle,
    OBConfig, OrderBlock, OBLifecycleEvent,
    OBDirection, OBStatus,
)


# ─── Helpers ─────────────────────────────────────────────────

def _dts(n, base=None, tf_min=5):
    if base is None:
        base = datetime(2025, 6, 16, 9, 30)
    return [base + timedelta(minutes=i * tf_min) for i in range(n)]


def _make_ms_event(bar_index, event_type, direction, evt_id=None):
    return {
        "bar_index": bar_index,
        "event_type": event_type,
        "direction": direction,
        "id": evt_id or bar_index,
    }


def _default_candles(n, base_price=50.0):
    """Create default bullish (close > open) candle arrays."""
    highs = [float(base_price + i * 0.5) for i in range(n)]
    lows = [float(base_price - 1 + i * 0.5) for i in range(n)]
    opens = [float(base_price + i * 0.5) for i in range(n)]
    closes = [float(base_price + 0.5 + i * 0.5) for i in range(n)]  # close > open
    volumes = [100.0] * n
    return highs, lows, opens, closes, volumes


# ─── Detection Tests ─────────────────────────────────────────

class TestOBDetection:
    """Order Block detection from Market Structure events."""

    def test_bullish_ob_from_bos(self):
        """Bullish BOS creates a bullish OB from the last bearish candle."""
        n = 10
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        opens = [float(49 + i) for i in range(n)]
        closes = [float(48.5 + i) for i in range(n)]
        volumes = [100.0] * n

        # Make candle at bar 4 bearish (close < open) before a BOS at bar 6
        opens[4] = 55.0; highs[4] = 56.0; lows[4] = 52.0; closes[4] = 53.0
        # Candle 5: neutral
        opens[5] = 55.0; highs[5] = 57.0; lows[5] = 53.0; closes[5] = 56.0

        ms_events = [_make_ms_event(6, "BOS", "bullish", 101)]
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        assert len(obs) >= 1, f"No OB found: {obs}"
        ob = obs[0]
        assert ob.direction == "bullish"
        assert ob.origin_candle_index == 4
        assert ob.related_ms_event_id == 101
        # Bullish OB: upper=high, lower=open (default config)
        assert ob.upper_bound == 56.0
        assert ob.lower_bound == 55.0

    def test_bearish_ob_from_bos(self):
        """Bearish BOS creates a bearish OB from the last bullish candle."""
        n = 10
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        opens = [float(49 + i) for i in range(n)]
        closes = [float(48.5 + i) for i in range(n)]
        volumes = [100.0] * n

        # Bullish candle at bar 3 (close > open) before bearish BOS at bar 5
        opens[3] = 52.0; highs[3] = 54.0; lows[3] = 50.0; closes[3] = 53.0
        opens[4] = 53.0; highs[4] = 55.0; lows[4] = 51.0; closes[4] = 52.0

        ms_events = [_make_ms_event(5, "BOS", "bearish", 201)]
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        assert len(obs) >= 1, f"No OB found"
        ob = obs[0]
        assert ob.direction == "bearish"
        assert ob.origin_candle_index == 3
        assert ob.related_ms_event_id == 201
        # Bearish OB: upper=open, lower=low
        assert ob.upper_bound == 52.0
        assert ob.lower_bound == 50.0

    def test_choch_creates_ob(self):
        """CHoCH events also create Order Blocks."""
        n = 10
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        opens = [float(49 + i) for i in range(n)]
        closes = [float(48.5 + i) for i in range(n)]
        volumes = [100.0] * n

        opens[2] = 54.0; highs[2] = 55.0; lows[2] = 50.0; closes[2] = 51.0  # bearish
        opens[3] = 52.0; highs[3] = 53.0; lows[3] = 50.0; closes[3] = 51.0

        ms_events = [_make_ms_event(4, "CHoCH", "bullish", 301)]
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        assert len(obs) >= 1

    def test_lookback_limit(self):
        """lookback_bars limits how far back we search for OB candle."""
        n = 15
        # Default candles: all BULLISH (close > open) — no spurious bearish candles
        highs = [float(55 + i) for i in range(n)]
        lows = [float(53 + i) for i in range(n)]
        opens = [float(54 + i) for i in range(n)]
        closes = [float(55 + i) for i in range(n)]  # close > open = bullish
        volumes = [100.0] * n

        # Only bearish candle at bar 2 (far back), BOS at bar 10
        opens[2] = 60.0; highs[2] = 61.0; lows[2] = 55.0; closes[2] = 57.0  # bearish

        ms_events = [_make_ms_event(10, "BOS", "bullish", 401)]
        config = OBConfig(lookback_bars=3)  # only looks back 3 bars from bar 10
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m", config,
        )
        # Bar 2 is 8 bars back → won't be found
        assert len(obs) == 0, f"Found OB at candle {[o.origin_candle_index for o in obs]}"

        config2 = OBConfig(lookback_bars=10)
        obs2 = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m", config2,
        )
        assert len(obs2) == 1

    def test_no_ms_event_no_ob(self):
        """Without BOS/CHoCH, no OBs are detected (require_bos_choch=True)."""
        n = 10
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        opens = [float(49 + i) for i in range(n)]
        closes = [float(48.5 + i) for i in range(n)]
        volumes = [100.0] * n

        opens[3] = 55.0; highs[3] = 56.0; lows[3] = 50.0; closes[3] = 52.0

        config = OBConfig(require_bos_choch=True)
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            [], "MNQ", "5m", config,
        )
        assert len(obs) == 0

    def test_use_open_close_bounds(self):
        """Config use_open_close_bounds changes the OB boundaries."""
        n = 10
        highs, lows, opens, closes, volumes = _default_candles(n)
        # Ensure only candle 4 is bearish
        for i in range(n):
            if i != 4:
                closes[i] = opens[i] + 0.5  # all bullish except 4

        opens[4] = 55.0; highs[4] = 58.0; lows[4] = 52.0; closes[4] = 53.0  # bearish
        ms_events = [_make_ms_event(6, "BOS", "bullish", 501)]

        config = OBConfig(use_open_close_bounds=True)
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m", config,
        )
        assert len(obs) == 1, f"Expected 1 OB, got {len(obs)}"
        ob = obs[0]
        assert ob.upper_bound == 55.0  # max(open, close)
        assert ob.lower_bound == 53.0  # min(open, close)

    def test_min_body_size_filter(self):
        """Candles with tiny bodies are filtered by min_body_size_pct."""
        n = 10
        highs, lows, opens, closes, volumes = _default_candles(n)
        for i in range(n):
            closes[i] = opens[i] + 0.5  # all bullish

        # Single bearish doji: open ≈ close (tiny body)
        opens[4] = 55.0; highs[4] = 58.0; lows[4] = 50.0; closes[4] = 55.02  # body=0.02, range=8 → 0.25%
        ms_events = [_make_ms_event(6, "BOS", "bullish", 601)]

        config = OBConfig(min_body_size_pct=1.0)  # requires ≥1% body
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m", config,
        )
        assert len(obs) == 0, f"Should have filtered tiny body, got {len(obs)}"

    def test_max_block_size_filter(self):
        """OBs with size > max_block_size_pct are filtered."""
        n = 10
        highs, lows, opens, closes, volumes = _default_candles(n)
        for i in range(n):
            closes[i] = opens[i] + 0.5  # all bullish

        # Large bearish candle: high=70, open=50 → block=20 → pct=33%
        opens[4] = 50.0; highs[4] = 70.0; lows[4] = 45.0; closes[4] = 48.0
        ms_events = [_make_ms_event(6, "BOS", "bullish", 701)]

        config = OBConfig(max_block_size_pct=10.0)  # max 10%, block is 33%
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m", config,
        )
        assert len(obs) == 0, f"Should filter large block, got {len(obs)}"

    def test_duplicate_prevention(self):
        """Same candle won't be used for multiple OBs."""
        n = 10
        highs, lows, opens, closes, volumes = _default_candles(n)
        for i in range(n):
            closes[i] = opens[i] + 0.5  # all bullish

        # Only ONE bearish candle at bar 3
        opens[3] = 55.0; highs[3] = 56.0; lows[3] = 50.0; closes[3] = 52.0
        # Two BOS events that would both look back to the same candle
        ms_events = [
            _make_ms_event(5, "BOS", "bullish", 801),
            _make_ms_event(6, "BOS", "bullish", 802),
        ]
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        assert len(obs) == 1, f"Expected dedup to 1, got {len(obs)}"


# ─── Lifecycle Tests ─────────────────────────────────────────

class TestOBLifecycle:
    """Order Block lifecycle management."""

    def _setup_bullish_ob_data(self, n=20):
        highs, lows, opens, closes, volumes = _default_candles(n)
        for i in range(n):
            closes[i] = opens[i] + 0.5  # all bullish

        # Single bearish candle at bar 4
        opens[4] = 55.0; highs[4] = 56.0; lows[4] = 52.0; closes[4] = 53.0
        opens[5] = 55.0; highs[5] = 57.0; lows[5] = 53.0; closes[5] = 56.0
        # Bars 7+: stay WITHIN the OB zone but not fully mitigating
        # OB is 55-56, so close=55.3 → 70% mitigation (not full)
        for j in range(7, n):
            highs[j] = 55.5; lows[j] = 54.8; closes[j] = 55.3

        ms_events = [_make_ms_event(6, "BOS", "bullish", 901)]
        return highs, lows, opens, closes, volumes, ms_events

    def test_ob_creation_event(self):
        """Every OB emits a creation event."""
        highs, lows, opens, closes, volumes, ms_events = self._setup_bullish_ob_data(10)
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(10),
            ms_events, "MNQ", "5m",
        )
        obs, events = apply_ob_lifecycle(obs, highs, lows, closes, _dts(10))
        created = [e for e in events if e.event_type == "created"]
        assert len(created) == 1

    def test_first_touch(self):
        """When price enters the OB zone, first_touch is recorded."""
        n = 15
        highs, lows, opens, closes, volumes, ms_events = self._setup_bullish_ob_data(n)
        # Bars 7+: default values produce overlapping bars (50-52 range)
        # OB is at 55-56. Default bars below won't touch it.
        # Make bar 10 touch the OB: price drops into 55-56 range
        highs[10] = 56.0; lows[10] = 54.0; closes[10] = 55.5

        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        obs, events = apply_ob_lifecycle(obs, highs, lows, closes, _dts(n))

        first_touch = [e for e in events if e.event_type == "first_touch"]
        assert len(first_touch) >= 1, f"Events: {[e.event_type for e in events]}"
        assert obs[0].first_touch_timestamp is not None

    def test_mitigation(self):
        """Full mitigation when price crosses entire OB range."""
        n = 15
        highs, lows, opens, closes, volumes = _default_candles(n)
        for i in range(n):
            closes[i] = opens[i] + 0.5  # all bullish

        # Bullish OB from bearish candle at bar 4: upper=56, lower=55
        opens[4] = 55.0; highs[4] = 56.0; lows[4] = 52.0; closes[4] = 53.0
        opens[5] = 55.0; highs[5] = 57.0; lows[5] = 53.0; closes[5] = 56.0

        # Bars 7-9: keep price BELOW upper bound (56) to avoid invalidation
        for j in range(7, 10):
            highs[j] = 55.5; lows[j] = 54.0; closes[j] = 55.0

        # Bar 10: price drops completely below OB lower bound (55)
        highs[10] = 56.0; lows[10] = 53.0; closes[10] = 54.0

        ms_events = [_make_ms_event(6, "BOS", "bullish", 901)]
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        obs, events = apply_ob_lifecycle(obs, highs, lows, closes, _dts(n))

        assert obs[0].status == "mitigated", f"Expected mitigated, got {obs[0].status}"

    def test_invalidation(self):
        """OB invalidated when price extends beyond in opposite direction."""
        n = 15
        highs, lows, opens, closes, volumes, ms_events = self._setup_bullish_ob_data(n)
        # Bar 10: price rallies well above OB upper bound
        # invalidation_pct default = 0.5% → 56 * 1.005 = 56.28
        highs[10] = 58.0; lows[10] = 56.0; closes[10] = 57.0  # > 56.28

        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        obs, events = apply_ob_lifecycle(obs, highs, lows, closes, _dts(n))

        assert obs[0].status == "invalidated", f"Got {obs[0].status}"

    def test_expiration_invalidation(self):
        """OB invalidated after expiration_bars."""
        n = 20
        highs, lows, opens, closes, volumes, ms_events = self._setup_bullish_ob_data(n)
        # Default bars: overlapping, OB at 55-56, untouched

        config = OBConfig(expiration_bars=5)
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m", config,
        )
        obs, events = apply_ob_lifecycle(obs, highs, lows, closes, _dts(n), config)

        assert obs[0].status == "invalidated"

    def test_bearish_ob_mitigation(self):
        """Bearish OB mitigated when price rallies up through it."""
        n = 15
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        opens = [float(49 + i) for i in range(n)]
        closes = [float(48.5 + i) for i in range(n)]
        volumes = [100.0] * n

        # Bullish candle at bar 3: bearish OB: upper=open=52, lower=low=50
        opens[3] = 52.0; highs[3] = 54.0; lows[3] = 50.0; closes[3] = 53.0
        opens[4] = 51.0; highs[4] = 53.0; lows[4] = 49.0; closes[4] = 50.0

        # Bar 10: price rallies up through OB (above 52)
        highs[10] = 54.0; lows[10] = 51.0; closes[10] = 53.0

        ms_events = [_make_ms_event(5, "BOS", "bearish", 1001)]
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        obs, events = apply_ob_lifecycle(obs, highs, lows, closes, _dts(n))

        assert obs[0].direction == "bearish"
        assert obs[0].status == "mitigated"


# ─── Edge Cases ──────────────────────────────────────────────

class TestOBEdgeCases:
    """Edge case and robustness tests."""

    def test_no_qualifying_candle(self):
        """No bearish candle found → no bullish OB."""
        n = 10
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        # All candles bullish (close > open)
        opens = [float(49 + i) for i in range(n)]
        closes = [float(50 + i) for i in range(n)]
        volumes = [100.0] * n

        ms_events = [_make_ms_event(5, "BOS", "bullish", 1101)]
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        assert len(obs) == 0

    def test_event_at_bar_0(self):
        """BOS at first bar — no lookback possible."""
        n = 10
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        opens = [float(49 + i) for i in range(n)]
        closes = [float(48.5 + i) for i in range(n)]
        volumes = [100.0] * n

        ms_events = [_make_ms_event(0, "BOS", "bullish", 1201)]
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        assert len(obs) == 0

    def test_non_bos_choch_ignored(self):
        """Non-BOS/CHoCH events don't create OBs."""
        n = 10
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        opens = [float(49 + i) for i in range(n)]
        closes = [float(48.5 + i) for i in range(n)]
        volumes = [100.0] * n

        opens[4] = 55.0; highs[4] = 56.0; lows[4] = 52.0; closes[4] = 53.0

        ms_events = [
            {"bar_index": 6, "event_type": "SWING_HIGH", "direction": "bullish", "id": 1301},
        ]
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m",
        )
        assert len(obs) == 0

    def test_timeframe_filter(self):
        """Config can restrict timeframes."""
        n = 10
        highs = [float(50 + i) for i in range(n)]
        lows = [float(48 + i) for i in range(n)]
        opens = [float(49 + i) for i in range(n)]
        closes = [float(48.5 + i) for i in range(n)]
        volumes = [100.0] * n

        opens[4] = 55.0; highs[4] = 56.0; lows[4] = 52.0; closes[4] = 53.0
        ms_events = [_make_ms_event(6, "BOS", "bullish", 1401)]

        config = OBConfig(enabled_timeframes=["1h", "4h"])
        obs = detect_order_blocks(
            highs, lows, opens, closes, volumes, _dts(n),
            ms_events, "MNQ", "5m", config,
        )
        assert len(obs) == 0


# ─── Config Tests ────────────────────────────────────────────

class TestOBConfig:
    """Configuration serialization."""

    def test_config_round_trip(self):
        config = OBConfig(
            lookback_bars=7,
            require_bos_choch=False,
            use_open_close_bounds=True,
            min_body_size_pct=2.0,
            max_block_size_pct=3.0,
            mitigation_method="wick",
            mitigation_threshold_pct=50.0,
            invalidation_pct=1.0,
            expiration_bars=200,
            enabled_timeframes=["5m", "15m"],
        )
        d = config.to_dict()
        c2 = OBConfig.from_dict(d)
        assert c2.lookback_bars == 7
        assert c2.require_bos_choch is False
        assert c2.use_open_close_bounds is True
        assert c2.mitigation_method == "wick"


# ─── API Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_ob_directions():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/order-blocks/directions")
        assert response.status_code == 200
        assert "bullish" in response.json()["directions"]


@pytest.mark.asyncio
async def test_list_ob_statuses():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/order-blocks/statuses")
        assert response.status_code == 200
        assert "mitigated" in response.json()["statuses"]
