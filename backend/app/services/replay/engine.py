"""Historical Replay Engine — deterministic bar-by-bar engine pipeline replay.

Feeds historical bars into the complete engine pipeline one bar at a time,
with strict no-lookahead enforcement. Uses a state machine: IDLE → RUNNING
→ PAUSED → STOPPED.

Architecture:
    Bar source (DB/CSV) → ReplayController → [MS, Liquidity, FVG, OB, SMT,
                                               Confluence, Strategy, Risk,
                                               Position Sizing, Trade Mgmt]
                                            → Snapshot + Events per bar
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


# ─── Enums ────────────────────────────────────────────────────

class ReplayState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class ReplayMode(str, Enum):
    CANDLE_BY_CANDLE = "candle_by_candle"
    CONTINUOUS = "continuous"
    UNTIL_TIMESTAMP = "until_timestamp"
    UNTIL_EVENT = "until_event"
    BY_SESSION = "by_session"
    BY_TRADING_DAY = "by_trading_day"


# ─── Bar Data ──────────────────────────────────────────────────

@dataclass
class OHLCVBar:
    """A single OHLCV bar — the canonical unit fed to engines during replay."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

    @classmethod
    def from_dict(cls, d: dict) -> OHLCVBar:
        ts = d.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return cls(
            timestamp=ts,
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=int(d.get("volume", 0)),
        )


# ─── Replay Config ────────────────────────────────────────────

@dataclass
class ReplayConfig:
    """Configuration for a replay session — all parameters externalized."""
    instrument: str = ""
    timeframe: str = "5m"
    start_time: datetime | None = None
    end_time: datetime | None = None
    mode: str = "candle_by_candle"

    # Engine pipeline ordering
    engine_order: list[str] = field(default_factory=lambda: [
        "market_structure",
        "liquidity",
        "fvg",
        "order_block",
        "smt",
        "confluence",
        "strategy",
        "risk",
        "position_sizing",
        "trade_management",
    ])

    # Session / day boundaries
    session_open_utc: int = 14  # 14:00 UTC = NY open
    session_close_utc: int = 21  # 21:00 UTC = NY close
    detect_session_boundaries: bool = True
    detect_day_boundaries: bool = True

    # Step/pause settings
    inter_bar_delay_ms: int = 0  # 0 = instant in continuous mode
    pause_on_session_boundary: bool = False
    pause_on_day_boundary: bool = False

    # Stop conditions
    max_bars: int = 0  # 0 = unlimited
    stop_on_event: str = ""  # Event type to stop on, empty = disabled
    stop_at_timestamp: datetime | None = None

    # Snapshot and event recording
    record_snapshots: bool = True
    record_events: bool = True

    # Engine callbacks (injected by pipeline integrator)
    engine_callbacks: list[tuple[str, Callable]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "mode": self.mode,
            "engine_order": list(self.engine_order),
            "session_open_utc": self.session_open_utc,
            "session_close_utc": self.session_close_utc,
            "detect_session_boundaries": self.detect_session_boundaries,
            "detect_day_boundaries": self.detect_day_boundaries,
            "inter_bar_delay_ms": self.inter_bar_delay_ms,
            "pause_on_session_boundary": self.pause_on_session_boundary,
            "pause_on_day_boundary": self.pause_on_day_boundary,
            "max_bars": self.max_bars,
            "stop_on_event": self.stop_on_event,
            "stop_at_timestamp": self.stop_at_timestamp.isoformat() if self.stop_at_timestamp else None,
            "record_snapshots": self.record_snapshots,
            "record_events": self.record_events,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ReplayConfig:
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        # Parse timestamps
        for key in ("start_time", "end_time", "stop_at_timestamp"):
            if key in valid and isinstance(valid[key], str):
                valid[key] = datetime.fromisoformat(valid[key])
        return cls(**valid)


# ─── Replay Snapshot ──────────────────────────────────────────

@dataclass
class ReplaySnapshot:
    """State snapshot captured after processing each bar."""
    instrument: str = ""
    timeframe: str = ""
    current_timestamp: datetime | None = None
    bar_index: int = 0
    candle: dict = field(default_factory=dict)
    market_structure_summary: dict = field(default_factory=dict)
    active_liquidity_count: int = 0
    active_fvg_count: int = 0
    active_ob_count: int = 0
    active_smt_count: int = 0
    confluence_snapshot_ref: int | None = None
    market_bias: dict = field(default_factory=dict)
    trade_setup_ref: str | None = None
    risk_report_ref: int | None = None
    position_sizing_ref: int | None = None
    trade_mgmt_state_ref: str | None = None

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "current_timestamp": self.current_timestamp.isoformat() if self.current_timestamp else None,
            "bar_index": self.bar_index,
            "candle": self.candle,
            "market_structure_summary": self.market_structure_summary,
            "active_liquidity_count": self.active_liquidity_count,
            "active_fvg_count": self.active_fvg_count,
            "active_ob_count": self.active_ob_count,
            "active_smt_count": self.active_smt_count,
            "confluence_snapshot_ref": self.confluence_snapshot_ref,
            "market_bias": self.market_bias,
            "trade_setup_ref": self.trade_setup_ref,
            "risk_report_ref": self.risk_report_ref,
            "position_sizing_ref": self.position_sizing_ref,
            "trade_mgmt_state_ref": self.trade_mgmt_state_ref,
        }


# ─── Replay Event ─────────────────────────────────────────────

@dataclass
class ReplayEvent:
    """Immutable record of an engine event during replay."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    replay_id: int = 0
    bar_index: int = 0
    timestamp: datetime | None = None
    engine_source: str = ""
    event_type: str = ""
    entity_ids: list[str] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "replay_id": self.replay_id,
            "bar_index": self.bar_index,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "engine_source": self.engine_source,
            "event_type": self.event_type,
            "entity_ids": self.entity_ids,
            "detail": self.detail,
        }


# ─── Replay Controller ────────────────────────────────────────

class ReplayController:
    """Deterministic historical replay engine with strict no-lookahead.

    State machine: IDLE → RUNNING → PAUSED → STOPPED.

    Feeds bars one at a time (ordered by timestamp ASC) into the configured
    engine pipeline. After each bar, captures a snapshot and records events.
    """

    def __init__(self, config: ReplayConfig | None = None):
        self.config = config or ReplayConfig()
        self._state: ReplayState = ReplayState.IDLE
        self._bars: list[OHLCVBar] = []
        self._bar_index: int = 0
        self._bar_count: int = 0
        self._snapshots: list[ReplaySnapshot] = []
        self._events: list[ReplayEvent] = []
        self._replay_id: int = 0
        self._session_id: str = ""
        self._engine_states: dict[str, Any] = {}
        self._previous_bar: OHLCVBar | None = None
        self._boundary_callbacks: list[Callable] = []
        self._event_callbacks: list[Callable] = []

    # ── State Machine ──────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state.value

    @property
    def bar_index(self) -> int:
        return self._bar_index

    @property
    def bar_count(self) -> int:
        return self._bar_count

    @property
    def current_bar(self) -> OHLCVBar | None:
        if 0 <= self._bar_index < len(self._bars):
            return self._bars[self._bar_index]
        return None

    @property
    def is_at_end(self) -> bool:
        return self._bar_index >= len(self._bars)

    @property
    def progress_pct(self) -> float:
        if self._bar_count == 0:
            return 0.0
        return round(min(self._bar_index / max(self._bar_count, 1), 1.0) * 100, 1)

    @property
    def snapshots(self) -> list[ReplaySnapshot]:
        return list(self._snapshots)

    @property
    def events(self) -> list[ReplayEvent]:
        return list(self._events)

    # ── Bar Loading ────────────────────────────────────────

    def load_bars(self, bars: list[OHLCVBar]) -> None:
        """Load bars into the controller. Bars MUST be sorted by timestamp ASC.

        This is the bar feeder — it provides the complete dataset for replay.
        The controller will only expose bars up to the current position.
        """
        # Ensure sorted by timestamp
        self._bars = sorted(bars, key=lambda b: b.timestamp)
        self._bar_count = len(self._bars)
        self._bar_index = 0

    def _get_visible_bars(self) -> list[OHLCVBar]:
        """Return only bars up to (and including) current position.

        CRITICAL: Never exposes bars with timestamp > current bar
        to any engine — this enforces the no-lookahead rule.
        """
        if self._state != ReplayState.RUNNING:
            return []
        if self._bar_index >= len(self._bars):
            return list(self._bars)
        return self._bars[:self._bar_index + 1]

    # ── Controls ───────────────────────────────────────────

    def start(self, replay_id: int = 0) -> ReplaySnapshot | None:
        """Start the replay from the beginning. Sets state to RUNNING at bar 0.

        The first bar is processed on the first call to step().
        """
        if self._state == ReplayState.RUNNING:
            return None
        if len(self._bars) == 0:
            self._state = ReplayState.IDLE
            return None

        self._state = ReplayState.RUNNING
        self._bar_index = 0
        self._replay_id = replay_id
        self._snapshots = []
        self._events = []
        self._previous_bar = None

        return None

    def pause(self) -> None:
        """Pause the replay at the current bar."""
        if self._state == ReplayState.RUNNING:
            self._state = ReplayState.PAUSED

    def resume(self) -> ReplaySnapshot | None:
        """Resume replay from paused state."""
        if self._state != ReplayState.PAUSED:
            return None
        self._state = ReplayState.RUNNING
        return self._process_current_bar()

    def stop(self) -> None:
        """Stop the replay."""
        self._state = ReplayState.STOPPED

    def reset(self) -> None:
        """Reset to IDLE state, clear all data."""
        self._state = ReplayState.IDLE
        self._bar_index = 0
        self._snapshots = []
        self._events = []
        self._previous_bar = None

    def step(self, n: int = 1) -> tuple[list[ReplaySnapshot], bool]:
        """Advance n bars forward. Returns (snapshots, is_at_end).

        In candle_by_candle mode, n defaults to 1.
        In continuous mode, this can be called repeatedly.
        """
        snapshots: list[ReplaySnapshot] = []
        if self._state not in (ReplayState.RUNNING, ReplayState.PAUSED):
            return snapshots, True

        # Ensure we're running for the step
        was_paused = self._state == ReplayState.PAUSED
        self._state = ReplayState.RUNNING

        for _ in range(n):
            if self.is_at_end:
                break
            snapshot = self._process_current_bar()
            if snapshot:
                snapshots.append(snapshot)
            self._bar_index += 1

        if was_paused:
            self._state = ReplayState.PAUSED

        if self.is_at_end:
            self._state = ReplayState.STOPPED

        return snapshots, self.is_at_end

    def jump_to(self, timestamp: datetime) -> ReplaySnapshot | None:
        """Jump to the bar at or immediately after the given timestamp.

        This advances the replay position to the specified timestamp,
        processing all intermediate bars (their snapshots/events are
        NOT recorded during the jump — only the final target bar is).
        """
        if self._state == ReplayState.IDLE:
            self._state = ReplayState.RUNNING

        if self._state not in (ReplayState.RUNNING, ReplayState.PAUSED):
            return None

        # Find the target index
        target_idx = self._bar_index  # Default: stay if can't find
        for i in range(self._bar_index, len(self._bars)):
            if self._bars[i].timestamp >= timestamp:
                target_idx = i
                break
        else:
            # All bars before timestamp — go to end
            target_idx = len(self._bars)
            self._state = ReplayState.STOPPED
            return None

        # Process all intermediate bars silently (no snapshot recording)
        was_recording = self.config.record_snapshots
        self.config.record_snapshots = False
        for i in range(self._bar_index, target_idx):
            self._process_current_bar()
            self._bar_index += 1
        self.config.record_snapshots = was_recording

        # Process the target bar with recording restored
        if self._bar_index < len(self._bars):
            return self._process_current_bar()

        if self._bar_index >= len(self._bars):
            self._state = ReplayState.STOPPED
        return None

    # ── Bar Processing ─────────────────────────────────────

    def _process_current_bar(self) -> ReplaySnapshot | None:
        """Process the current bar through the engine pipeline.

        This is the core replay logic — feeds the current bar to each
        engine in order, captures a snapshot, and records events.
        """
        if self._bar_index >= len(self._bars):
            self._state = ReplayState.STOPPED
            return None

        bar = self._bars[self._bar_index]

        # Check stop conditions
        if self.config.max_bars > 0 and self._bar_index >= self.config.max_bars:
            self._state = ReplayState.STOPPED
            return None

        if self.config.stop_at_timestamp and bar.timestamp >= self.config.stop_at_timestamp:
            self._state = ReplayState.STOPPED
            return None

        # Detect boundaries
        boundary = self._detect_boundaries(bar)

        # Execute engine callbacks in order
        bar_events: list[ReplayEvent] = []
        engine_outputs: dict[str, Any] = {}

        visible_bars = self._get_visible_bars()
        for engine_name, callback in self.config.engine_callbacks:
            try:
                result = callback(
                    bar=bar,
                    visible_bars=visible_bars,
                    engine_states=self._engine_states,
                    previous_bar=self._previous_bar,
                    boundary=boundary,
                )
                engine_outputs[engine_name] = result

                # Collect events from engine output
                engine_events = self._extract_events(engine_name, result)
                bar_events.extend(engine_events)
            except Exception as e:
                # Record engine failure as an event
                evt = ReplayEvent(
                    replay_id=self._replay_id,
                    bar_index=self._bar_index,
                    timestamp=bar.timestamp,
                    engine_source=engine_name,
                    event_type="engine_error",
                    detail=str(e),
                )
                bar_events.append(evt)
                if self.config.record_events:
                    self._events.append(evt)

        # Check stop_on_event
        if self.config.stop_on_event:
            for evt in bar_events:
                if evt.event_type == self.config.stop_on_event:
                    self._state = ReplayState.STOPPED
                    break

        # Build snapshot
        snapshot = ReplaySnapshot(
            instrument=self.config.instrument,
            timeframe=self.config.timeframe,
            current_timestamp=bar.timestamp,
            bar_index=self._bar_index,
            candle=bar.to_dict(),
            market_structure_summary=engine_outputs.get("market_structure", {}),
            active_liquidity_count=engine_outputs.get("liquidity_count", 0),
            active_fvg_count=engine_outputs.get("fvg_count", 0),
            active_ob_count=engine_outputs.get("ob_count", 0),
            active_smt_count=engine_outputs.get("smt_count", 0),
            confluence_snapshot_ref=engine_outputs.get("confluence_ref"),
            market_bias=engine_outputs.get("market_bias", {}),
            trade_setup_ref=engine_outputs.get("trade_setup_ref"),
            risk_report_ref=engine_outputs.get("risk_report_ref"),
            position_sizing_ref=engine_outputs.get("position_sizing_ref"),
            trade_mgmt_state_ref=engine_outputs.get("trade_mgmt_state_ref"),
        )

        if self.config.record_snapshots:
            self._snapshots.append(snapshot)

        # Record events
        if self.config.record_events:
            self._events.extend(bar_events)

        # Fire event callbacks
        for cb in self._event_callbacks:
            try:
                cb(bar_events)
            except Exception:
                pass

        # Fire boundary callbacks
        if boundary["is_session_boundary"] or boundary["is_day_boundary"]:
            for cb in self._boundary_callbacks:
                try:
                    cb(boundary)
                except Exception:
                    pass

            if boundary["is_session_boundary"] and self.config.pause_on_session_boundary:
                self._state = ReplayState.PAUSED
            if boundary["is_day_boundary"] and self.config.pause_on_day_boundary:
                self._state = ReplayState.PAUSED

        self._previous_bar = bar
        return snapshot

    def _detect_boundaries(self, bar: OHLCVBar) -> dict:
        """Detect session and day boundaries for the current bar."""
        result = {
            "is_session_boundary": False,
            "is_day_boundary": False,
            "session": "unknown",
        }

        if not self._previous_bar:
            return result

        if self.config.detect_day_boundaries:
            prev_day = self._previous_bar.timestamp.date()
            cur_day = bar.timestamp.date()
            if cur_day != prev_day:
                result["is_day_boundary"] = True

        if self.config.detect_session_boundaries:
            prev_hour = self._previous_bar.timestamp.hour
            cur_hour = bar.timestamp.hour
            # Session boundary when crossing open or close
            if (prev_hour < self.config.session_open_utc <= cur_hour):
                result["is_session_boundary"] = True
                result["session"] = "ny_am"
            elif (prev_hour < self.config.session_close_utc <= cur_hour):
                result["is_session_boundary"] = True
                result["session"] = "after_hours"

        return result

    def _extract_events(self, engine_name: str, result: Any) -> list[ReplayEvent]:
        """Extract replay events from engine callback results."""
        events: list[ReplayEvent] = []
        if result is None:
            return events

        bar = self.current_bar
        if bar is None:
            return events

        if isinstance(result, dict):
            inner_events = result.get("events", [])
            if isinstance(inner_events, list):
                for e in inner_events:
                    if isinstance(e, dict):
                        events.append(ReplayEvent(
                            replay_id=self._replay_id,
                            bar_index=self._bar_index,
                            timestamp=bar.timestamp,
                            engine_source=engine_name,
                            event_type=str(e.get("event_type", "")),
                            entity_ids=e.get("entity_ids", []),
                            detail=str(e.get("detail", "")),
                        ))

        return events

    def register_event_callback(self, callback: Callable) -> None:
        """Register a callback that fires after each bar's events are recorded."""
        self._event_callbacks.append(callback)

    def register_boundary_callback(self, callback: Callable) -> None:
        """Register a callback that fires on session/day boundaries."""
        self._boundary_callbacks.append(callback)

    # ── Dry Run ────────────────────────────────────────────

    def dry_run(self) -> list[ReplaySnapshot]:
        """Run the entire replay from start to finish, return all snapshots.

        Deterministic: same input bars → same output every time.
        """
        self.reset()
        self._state = ReplayState.RUNNING
        snapshots: list[ReplaySnapshot] = []

        while self._bar_index < len(self._bars):
            snapshot = self._process_current_bar()
            if snapshot:
                snapshots.append(snapshot)
            self._bar_index += 1

        self._state = ReplayState.STOPPED
        return snapshots

    # ── State Import / Export ──────────────────────────────

    def export_state(self) -> dict:
        """Export controller state for persistence."""
        return {
            "state": self._state.value,
            "bar_index": self._bar_index,
            "bar_count": self._bar_count,
            "replay_id": self._replay_id,
            "config": self.config.to_dict(),
            "snapshot_count": len(self._snapshots),
            "event_count": len(self._events),
        }

    def import_state(self, state: dict) -> None:
        """Restore controller state from export."""
        self._state = ReplayState(state.get("state", "idle"))
        self._bar_index = int(state.get("bar_index", 0))
        self._bar_count = int(state.get("bar_count", 0))
        self._replay_id = int(state.get("replay_id", 0))
