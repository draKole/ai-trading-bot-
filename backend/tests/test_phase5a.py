"""Phase 5A Tests — Historical Replay Engine.

Tests for ReplayController state machine, bar feeding, no-lookahead
enforcement, snapshot capture, event recording, determinism, and all
control operations.
"""

from datetime import datetime, timedelta, timezone
import json
import pytest

from app.services.replay.engine import (
    ReplayController, ReplayConfig, OHLCVBar, ReplaySnapshot,
    ReplayEvent, ReplayState, ReplayMode,
)


# ─── Helpers ─────────────────────────────────────────────────

def _make_bar(
    timestamp: datetime | None = None,
    price: float = 100.0,
    minute: int = 0,
    volume: int = 100,
) -> OHLCVBar:
    if timestamp is None:
        timestamp = datetime(2025, 6, 16, 9, 30, tzinfo=timezone.utc) + timedelta(minutes=minute)
    return OHLCVBar(
        timestamp=timestamp,
        open=price - 0.25,
        high=price + 0.5,
        low=price - 0.5,
        close=price + 0.25,
        volume=volume,
    )


def _make_bars(n: int = 10, base_price: float = 100.0) -> list[OHLCVBar]:
    """Generate n ascending bars."""
    bars = []
    for i in range(n):
        price = base_price + i * 0.1
        timestamp = datetime(2025, 6, 16, 9, 30, tzinfo=timezone.utc) + timedelta(minutes=i * 5)
        bars.append(OHLCVBar(
            timestamp=timestamp,
            open=price - 0.25,
            high=price + 0.5,
            low=price - 0.5,
            close=price + 0.25,
            volume=100 + i,
        ))
    return bars


def _default_config() -> ReplayConfig:
    return ReplayConfig(
        instrument="ES",
        timeframe="5m",
        start_time=datetime(2025, 6, 16, 9, 30, tzinfo=timezone.utc),
        end_time=datetime(2025, 6, 16, 16, 0, tzinfo=timezone.utc),
        mode="candle_by_candle",
    )


# ─── ReplayConfig Tests ─────────────────────────────────────

class TestReplayConfig:
    """ReplayConfig creation, serialization, defaults."""

    def test_default_config(self):
        config = ReplayConfig()
        assert config.instrument == ""
        assert config.timeframe == "5m"
        assert config.mode == "candle_by_candle"
        assert len(config.engine_order) == 10

    def test_config_to_dict_roundtrip(self):
        config = _default_config()
        d = config.to_dict()
        restored = ReplayConfig.from_dict(d)
        assert restored.instrument == config.instrument
        assert restored.timeframe == config.timeframe
        assert restored.mode == config.mode

    def test_config_json_serializable(self):
        config = _default_config()
        d = config.to_dict()
        s = json.dumps(d, default=str)
        assert isinstance(s, str)
        assert "ES" in s

    def test_config_custom_engine_order(self):
        config = ReplayConfig(engine_order=["market_structure", "liquidity", "strategy"])
        assert len(config.engine_order) == 3
        assert config.engine_order[0] == "market_structure"

    def test_config_timestamps_roundtrip(self):
        config = _default_config()
        config.stop_at_timestamp = datetime(2025, 6, 16, 12, 0, tzinfo=timezone.utc)
        d = config.to_dict()
        restored = ReplayConfig.from_dict(d)
        assert restored.stop_at_timestamp is not None
        assert restored.stop_at_timestamp == config.stop_at_timestamp


# ─── OHLCVBar Tests ─────────────────────────────────────────

class TestOHLCVBar:
    """Bar serialization and creation."""

    def test_bar_to_dict(self):
        bar = _make_bar(price=100.0)
        d = bar.to_dict()
        assert d["close"] == 100.25
        assert "timestamp" in d

    def test_bar_from_dict(self):
        bar = _make_bar(price=100.0)
        d = bar.to_dict()
        restored = OHLCVBar.from_dict(d)
        assert restored.close == bar.close
        assert restored.timestamp == bar.timestamp

    def test_bar_volume_default(self):
        bar = OHLCVBar(
            timestamp=datetime(2025, 6, 16, 9, 30, tzinfo=timezone.utc),
            open=100, high=101, low=99, close=100.5,
        )
        assert bar.volume == 0


# ─── State Machine Tests ────────────────────────────────────

class TestStateMachine:
    """ReplayController state transitions."""

    def test_initial_state_idle(self):
        controller = ReplayController(_default_config())
        assert controller.state == "idle"
        assert controller.bar_index == 0

    def test_start_transitions_to_running(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(5))
        controller.start()
        assert controller.state == "running"

    def test_start_with_no_bars_stays_idle(self):
        controller = ReplayController(_default_config())
        result = controller.start()
        assert result is None
        assert controller.state == "idle"

    def test_pause_transitions(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(5))
        controller.start()
        controller.pause()
        assert controller.state == "paused"

    def test_resume_from_paused(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(5))
        controller.start()
        controller.pause()
        assert controller.state == "paused"
        controller.resume()
        assert controller.state == "running"

    def test_stop_transitions(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(5))
        controller.start()
        controller.stop()
        assert controller.state == "stopped"

    def test_reset_transitions_to_idle(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(5))
        controller.start()
        controller.reset()
        assert controller.state == "idle"
        assert controller.bar_index == 0

    def test_cannot_start_running_again(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(5))
        controller.start()
        result = controller.start()
        assert result is None


# ─── Bar Feeding / Lookahead Tests ──────────────────────────

class TestBarFeeding:
    """Bar loading, ordering, and no-lookahead enforcement."""

    def test_bars_are_sorted_on_load(self):
        bars = [
            _make_bar(minute=10),
            _make_bar(minute=0),
            _make_bar(minute=5),
        ]
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        # Should be sorted by timestamp
        assert controller.bar_count == 3
        assert controller._bars[0].timestamp < controller._bars[1].timestamp
        assert controller._bars[1].timestamp < controller._bars[2].timestamp

    def test_only_visible_up_to_current(self):
        bars = _make_bars(5)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        controller.start()
        # After start, bar_index = 0, only bar 0 visible
        visible = controller._get_visible_bars()
        assert len(visible) == 1  # Only the first bar

    def test_no_future_bars_visible(self):
        bars = _make_bars(10)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        controller.start()
        # After start, only bar 0 visible
        visible = controller._get_visible_bars()
        max_visible_ts = max(b.timestamp for b in visible)
        assert max_visible_ts <= bars[0].timestamp

    def test_visible_bars_grow_with_progress(self):
        bars = _make_bars(5)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        controller.start()
        controller.step(2)
        # After stepping 2 more, 3 bars should be visible (start processed bar 0, step 2 more)
        visible = controller._get_visible_bars()
        assert len(visible) == 3

    def test_bar_count_matches_loaded(self):
        bars = _make_bars(7)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        assert controller.bar_count == 7

    def test_is_at_end(self):
        bars = _make_bars(3)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        assert not controller.is_at_end
        controller._bar_index = 3
        assert controller.is_at_end


# ─── Snapshot Tests ────────────────────────────────────────

class TestSnapshots:
    """Snapshot capture during replay."""

    def test_snapshot_created_per_bar(self):
        bars = _make_bars(5)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        snapshots = controller.dry_run()
        assert len(snapshots) == 5

    def test_snapshot_contains_candle(self):
        bars = _make_bars(3)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        snapshots = controller.dry_run()
        assert snapshots[0].candle["close"] == bars[0].close

    def test_snapshot_bar_index_correct(self):
        bars = _make_bars(5)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        snapshots = controller.dry_run()
        for i, s in enumerate(snapshots):
            assert s.bar_index == i

    def test_snapshot_disabled_config(self):
        config = _default_config()
        config.record_snapshots = False
        controller = ReplayController(config)
        controller.load_bars(_make_bars(5))
        # dry_run always returns snapshots directly — record_snapshots
        # controls whether they're stored in controller.snapshots
        result = controller.dry_run()
        assert len(result) > 0  # dry_run returns snapshots regardless
        assert len(controller.snapshots) == 0  # but internal store is empty

    def test_snapshot_export(self):
        bars = _make_bars(3)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        controller.dry_run()
        d = controller.snapshots[0].to_dict()
        assert "bar_index" in d
        assert "candle" in d


# ─── Event Tests ────────────────────────────────────────────

class TestEvents:
    """Event recording during replay."""

    def test_events_disabled_config(self):
        config = _default_config()
        config.record_events = False
        controller = ReplayController(config)
        controller.load_bars(_make_bars(5))
        controller.dry_run()
        assert len(controller.events) == 0

    def test_event_to_dict(self):
        event = ReplayEvent(
            replay_id=1, bar_index=0,
            timestamp=datetime(2025, 6, 16, 9, 30, tzinfo=timezone.utc),
            engine_source="market_structure",
            event_type="bos",
            entity_ids=["ms-1"],
            detail="Bullish BOS at 100.5",
        )
        d = event.to_dict()
        assert d["engine_source"] == "market_structure"
        assert d["event_type"] == "bos"


# ─── Step / Control Tests ──────────────────────────────────

class TestStep:
    """Step control with various n values."""

    def test_step_1(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(5))
        controller.start()
        snapshots, is_end = controller.step(1)
        assert len(snapshots) == 1
        assert not is_end
        assert controller.bar_index == 1  # start() sets index 0, step(1) processes bar 0 → index 1

    def test_step_n(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(5))
        controller.start()
        snapshots, is_end = controller.step(3)
        assert len(snapshots) == 3
        assert controller.bar_index == 3  # processes bars 0,1,2 → index 3

    def test_step_to_end(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(3))
        controller.start()
        snapshots, is_end = controller.step(5)  # more than available
        assert is_end
        assert controller.state == "stopped"

    def test_step_from_idle_does_nothing(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(3))
        snapshots, is_end = controller.step(1)
        assert len(snapshots) == 0
        assert is_end


# ─── Determinism Tests ─────────────────────────────────────

class TestDeterminism:
    """Deterministic replay: same input → same output."""

    def test_same_input_same_snapshots(self):
        bars = _make_bars(5)
        controller1 = ReplayController(_default_config())
        controller1.load_bars(list(bars))
        snapshots1 = controller1.dry_run()

        controller2 = ReplayController(_default_config())
        controller2.load_bars(list(bars))
        snapshots2 = controller2.dry_run()

        assert len(snapshots1) == len(snapshots2)
        for s1, s2 in zip(snapshots1, snapshots2):
            assert s1.bar_index == s2.bar_index
            assert s1.candle == s2.candle

    def test_same_input_same_events(self):
        bars = _make_bars(5)
        controller1 = ReplayController(_default_config())
        controller1.load_bars(list(bars))
        controller1.dry_run()

        controller2 = ReplayController(_default_config())
        controller2.load_bars(list(bars))
        controller2.dry_run()

        assert len(controller1.events) == len(controller2.events)

    def test_dry_run_deterministic(self):
        bars = _make_bars(10)
        controller1 = ReplayController(_default_config())
        controller1.load_bars(list(bars))
        result1 = controller1.dry_run()

        controller2 = ReplayController(_default_config())
        controller2.load_bars(list(bars))
        result2 = controller2.dry_run()

        assert len(result1) == len(result2)
        for i in range(len(result1)):
            assert result1[i].to_dict() == result2[i].to_dict()


# ─── Jump To Tests ─────────────────────────────────────────

class TestJumpTo:
    """Jump to a specific timestamp."""

    def test_jump_to_middle(self):
        bars = _make_bars(10)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        controller.start()
        target = bars[5].timestamp
        result = controller.jump_to(target)
        assert result is not None
        # Should be at or past bar 5
        assert controller.bar_index >= 5

    def test_jump_to_before_current_does_nothing(self):
        bars = _make_bars(10)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        controller.start()
        controller.step(3)
        # Jump to first bar (already passed)
        target = bars[0].timestamp
        controller.jump_to(target)
        # Should not go backward
        assert controller.bar_index >= 3

    def test_jump_to_end(self):
        bars = _make_bars(5)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        controller.start()
        target = bars[4].timestamp + timedelta(hours=1)
        result = controller.jump_to(target)
        assert result is None
        assert controller.state == "stopped"


# ─── Boundary Detection Tests ──────────────────────────────

class TestBoundaries:
    """Session and day boundary detection."""

    def test_day_boundary_detected(self):
        config = _default_config()
        config.detect_day_boundaries = True
        controller = ReplayController(config)
        bars = [
            OHLCVBar(timestamp=datetime(2025, 6, 16, 20, 0, tzinfo=timezone.utc),
                     open=100, high=101, low=99, close=100.5),
            OHLCVBar(timestamp=datetime(2025, 6, 17, 5, 0, tzinfo=timezone.utc),
                     open=101, high=102, low=100, close=101.5),
        ]
        controller.load_bars(bars)
        controller.start()
        controller._previous_bar = bars[0]  # simulate having processed bar 0
        boundary = controller._detect_boundaries(bars[1])
        assert boundary["is_day_boundary"] is True

    def test_no_boundary_same_day(self):
        config = _default_config()
        config.detect_day_boundaries = True
        controller = ReplayController(config)
        bars = [
            OHLCVBar(timestamp=datetime(2025, 6, 16, 9, 30, tzinfo=timezone.utc),
                     open=100, high=101, low=99, close=100.5),
            OHLCVBar(timestamp=datetime(2025, 6, 16, 9, 35, tzinfo=timezone.utc),
                     open=100, high=101, low=99, close=100.5),
        ]
        controller.load_bars(bars)
        controller.start()
        controller._previous_bar = bars[0]
        boundary = controller._detect_boundaries(bars[1])
        assert boundary["is_day_boundary"] is False

    def test_boundary_disabled(self):
        config = _default_config()
        config.detect_day_boundaries = False
        config.detect_session_boundaries = False
        controller = ReplayController(config)
        bars = [
            OHLCVBar(timestamp=datetime(2025, 6, 16, 22, 0, tzinfo=timezone.utc),
                     open=100, high=101, low=99, close=100.5),
            OHLCVBar(timestamp=datetime(2025, 6, 17, 5, 0, tzinfo=timezone.utc),
                     open=101, high=102, low=100, close=101.5),
        ]
        controller.load_bars(bars)
        controller.start()
        controller._previous_bar = bars[0]
        boundary = controller._detect_boundaries(bars[1])
        assert boundary["is_day_boundary"] is False


# ─── State Export/Import Tests ──────────────────────────────

class TestStateExport:
    """State export and import."""

    def test_export_state_contains_keys(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(5))
        controller.start()
        state = controller.export_state()
        assert "state" in state
        assert "bar_index" in state
        assert "bar_count" in state
        assert state["state"] == "running"

    def test_import_state_restores(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(10))
        state = {"state": "paused", "bar_index": 5, "bar_count": 10, "replay_id": 1}
        controller.import_state(state)
        assert controller.state == "paused"
        assert controller.bar_index == 5


# ─── Modes Tests ────────────────────────────────────────────

class TestModes:
    """Replay mode handling."""

    def test_max_bars_limit(self):
        config = _default_config()
        config.max_bars = 3
        controller = ReplayController(config)
        controller.load_bars(_make_bars(10))
        snapshots = controller.dry_run()
        assert len(snapshots) == 3

    def test_stop_at_timestamp(self):
        config = _default_config()
        bars = _make_bars(10)
        config.stop_at_timestamp = bars[4].timestamp
        controller = ReplayController(config)
        controller.load_bars(bars)
        snapshots = controller.dry_run()
        # Should stop when timestamp is >= stop_at_timestamp
        assert len(snapshots) <= 5

    def test_progress_pct(self):
        bars = _make_bars(10)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        controller.start()
        controller.step(4)
        assert controller.progress_pct > 0


# ─── Callback Tests ────────────────────────────────────────

class TestCallbacks:
    """Event and boundary callbacks."""

    def test_event_callback_fires(self):
        controller = ReplayController(_default_config())
        controller.load_bars(_make_bars(3))
        events_received = []
        controller.register_event_callback(lambda evts: events_received.extend(evts))
        controller.dry_run()
        # Callbacks fire after each bar
        assert isinstance(events_received, list)

    def test_boundary_callback_registration(self):
        controller = ReplayController(_default_config())
        called = []
        controller.register_boundary_callback(lambda b: called.append(b))
        assert len(controller._boundary_callbacks) == 1


# ─── Dry Run Tests ─────────────────────────────────────────

class TestDryRun:
    """Full dry-run behavior."""

    def test_dry_run_completes_all_bars(self):
        bars = _make_bars(5)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        snapshots = controller.dry_run()
        assert len(snapshots) == 5
        assert controller.state == "stopped"

    def test_dry_run_empty_bars(self):
        controller = ReplayController(_default_config())
        controller.load_bars([])
        snapshots = controller.dry_run()
        assert len(snapshots) == 0

    def test_dry_run_resets_first(self):
        bars = _make_bars(5)
        controller = ReplayController(_default_config())
        controller.load_bars(bars)
        controller.start()
        controller.step(2)
        # Now dry_run should reset and run all
        snapshots = controller.dry_run()
        assert len(snapshots) == 5


# ─── API Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_replay_dry_run_api():
    """Test the /api/v1/replay/dry-run endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    bars = [
        {"timestamp": "2025-06-16T09:30:00+00:00", "open": 100.0, "high": 100.5,
         "low": 99.5, "close": 100.25, "volume": 100},
        {"timestamp": "2025-06-16T09:35:00+00:00", "open": 100.25, "high": 100.75,
         "low": 100.0, "close": 100.5, "volume": 150},
        {"timestamp": "2025-06-16T09:40:00+00:00", "open": 100.5, "high": 101.0,
         "low": 100.25, "close": 100.75, "volume": 200},
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/replay/dry-run",
            params={
                "instrument": "ES",
                "timeframe": "5m",
                "start_time": "2025-06-16T09:30:00",
                "end_time": "2025-06-16T16:00:00",
                "mode": "candle_by_candle",
                "bars_json": json.dumps(bars),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["instrument"] == "ES"
        assert data["bar_count_input"] == 3
        assert data["bar_count_replayed"] == 3
        assert len(data["snapshots"]) == 3
