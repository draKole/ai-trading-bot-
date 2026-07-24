# Historical Replay Engine — Deterministic Bar-by-Bar Pipeline Replay

## Overview

The Historical Replay Engine feeds historical OHLCV bars through the complete engine pipeline one bar at a time, with strict no-lookahead enforcement. It is the foundation for backtesting, strategy validation, and historical analysis. Every replay is deterministic: same input bars → same output every time (excluding generated IDs/timestamps).

## Architecture

```
Bar Source (DB/CSV) → ReplayController (state machine)
                           ↓
                    [bar index N: only bars [0..N] visible]
                           ↓
         Engine Pipeline (in configured order):
           market_structure → liquidity → fvg → order_block
              → smt → confluence → strategy → risk
                 → position_sizing → trade_management
                           ↓
                    ReplaySnapshot (per bar)
                    ReplayEvent[] (per engine, per bar)
```

---

## 1. ReplayController — State Machine

```
IDLE ──start()──▶ RUNNING ──pause()──▶ PAUSED
  ▲                  │                     │
  │                  │       resume()      │
  │                  │◀────────────────────┘
  │                  │
  │               stop()                   step(n)
  │                  │                     │
  │                  ▼                     ▼
  └────reset()─── STOPPED              RUNNING (advances N bars)
```

### Controls

| Method | Description |
|--------|-------------|
| `start()` | Initialize replay at bar 0, set state to RUNNING |
| `pause()` | Pause at current bar |
| `resume()` | Resume from PAUSED — reprocesses current bar |
| `stop()` | Halt replay |
| `reset()` | Return to IDLE, clear snapshots and events |
| `step(n=1)` | Process N bars. Returns (snapshots, is_at_end) |
| `jump_to(ts)` | Advance to bar at/after timestamp (intermediate bars not recorded) |
| `dry_run()` | Run start→finish, return all snapshots |

### ReplayConfig — All Parameters Externalized

| Parameter | Default | Description |
|-----------|---------|-------------|
| `instrument` | `""` | Trading instrument |
| `timeframe` | `"5m"` | Bar timeframe |
| `start_time` / `end_time` | None | Time boundaries |
| `mode` | `candle_by_candle` | One of 6 modes |
| `engine_order` | 10 engines | Pipeline call order |
| `max_bars` | 0 (unlimited) | Hard stop after N bars |
| `stop_at_timestamp` | None | Halt at/after timestamp |
| `stop_on_event` | `""` | Halt on event type match |
| `record_snapshots` | True | Persist per-bar snapshots |
| `record_events` | True | Persist engine events |
| `detect_session_boundaries` | True | NY session open/close |
| `detect_day_boundaries` | True | Calendar day crossings |
| `pause_on_session_boundary` | False | Auto-pause at session boundary |
| `pause_on_day_boundary` | False | Auto-pause at day boundary |

### Replay Modes

| Mode | Behavior |
|------|----------|
| `candle_by_candle` | Step one bar at a time (default) |
| `continuous` | Run until stopped or end-of-data |
| `until_timestamp` | Run until reaching a target timestamp |
| `until_event` | Run until a specific engine event fires |
| `by_session` | Run one trading session at a time |
| `by_trading_day` | Run one calendar day at a time |

---

## 2. ReplaySnapshot — Per-Bar State Capture

After each bar is processed through the pipeline, a snapshot captures:

| Field | Description |
|-------|-------------|
| `instrument` | Trading instrument |
| `timeframe` | Bar timeframe |
| `current_timestamp` | Bar timestamp |
| `bar_index` | 0-based position in replay |
| `candle` | OHLCV dict (open, high, low, close, volume) |
| `market_structure_summary` | MS engine output (swings, BOS, CHoCH) |
| `active_liquidity_count` | Count of active liquidity levels |
| `active_fvg_count` | Count of active fair value gaps |
| `active_ob_count` | Count of active order blocks |
| `active_smt_count` | Count of SMT divergence events |
| `confluence_snapshot_ref` | Reference to latest confluence snapshot |
| `market_bias` | Directional bias dict |
| `trade_setup_ref` | Reference to active trade setup |
| `risk_report_ref` | Reference to risk evaluation |
| `position_sizing_ref` | Reference to position recommendation |
| `trade_mgmt_state_ref` | Reference to trade management state |

---

## 3. ReplayEvent — Engine Event Record

Every engine output event is captured as an immutable record:

| Field | Description |
|-------|-------------|
| `event_id` | UUID |
| `replay_id` | Parent replay session |
| `bar_index` | Bar position when event fired |
| `timestamp` | Bar timestamp |
| `engine_source` | Which engine produced it |
| `event_type` | Event classification |
| `entity_ids` | Referenced entity IDs (JSON) |
| `detail` | Human-readable description |

---

## 4. No-Lookahead Guarantee

**This is non-negotiable.** The replay engine enforces:

1. Bar at index N can only see bars `[0..N]` — strictly inclusive.
2. `_get_visible_bars()` returns `bars[:bar_index + 1]` — never exposes future data.
3. Only called during RUNNING state — PAUSED/STOPPED/IDLE return empty.
4. `load_bars()` sorts by timestamp ASC on ingest.
5. `jump_to()` processes intermediate bars silently (no snapshot recording) to reach target.
6. Engine callbacks receive `visible_bars` (not `bars`) — they cannot access future data.

---

## 5. Determinism

Same input → same output every time:

1. Bars sorted deterministically (by timestamp ASC, stable sort).
2. Engine pipeline order is fixed per config.
3. No randomness in processing — no random seeds, no stochastic elements.
4. `dry_run()` resets state before running, ensuring clean start.
5. IDs and timestamps are generated but do not affect engine logic.

Verified by `test_dry_run_deterministic` and `test_same_input_same_snapshots`.

---

## 6. Engine Pipeline Integration

The controller is an orchestrator — it does not duplicate engine logic. Engines are called through `engine_callbacks` — a list of `(name, callable)` tuples. Each callback receives:

```python
callback(bar, visible_bars, engine_states, previous_bar, boundary)
```

- `bar`: The current OHLCVBar being processed
- `visible_bars`: All bars up to current index (for stateful engines)
- `engine_states`: Mutable dict for engines to persist state across bars
- `previous_bar`: The immediately preceding bar
- `boundary`: Dict with `is_session_boundary`, `is_day_boundary`, `session`

Engine outputs are collected in `engine_outputs` and used to build the snapshot.

---

## 7. Database Schema

### `replay_sessions` — 12 columns
id, instrument, timeframe, start_time, end_time, mode, status, bar_count, bar_index, current_timestamp, config_json, created_at, updated_at.

Indexes: instrument, status.

### `replay_snapshots` — 6 columns
id, replay_id (FK→replay_sessions), bar_index, timestamp, candle_json, summary_json.

Index: replay_id.

### `replay_events` — 9 columns
id, replay_id (FK→replay_sessions), bar_index, timestamp, engine_source, event_type, entity_ids_json, detail, created_at.

Index: replay_id.

---

## 8. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/replay/sessions` | List replay sessions |
| `GET` | `/api/v1/replay/sessions/{id}` | Get session details |
| `POST` | `/api/v1/replay/sessions/start` | Create session + optional dry-run |
| `POST` | `/api/v1/replay/sessions/{id}/pause` | Pause running session |
| `POST` | `/api/v1/replay/sessions/{id}/resume` | Resume paused session |
| `POST` | `/api/v1/replay/sessions/{id}/reset` | Reset to idle |
| `POST` | `/api/v1/replay/sessions/{id}/step` | Step N bars forward |
| `GET` | `/api/v1/replay/sessions/{id}/status` | Current replay status |
| `GET` | `/api/v1/replay/sessions/{id}/events` | Events with filters |
| `GET` | `/api/v1/replay/sessions/{id}/snapshots` | Snapshots list |
| `POST` | `/api/v1/replay/dry-run` | Stateless dry-run (no DB) |

---

## 9. Limitations

1. Engine callbacks must be registered explicitly — no auto-discovery of engines.
2. `jump_to()` does not record intermediate snapshots (by design — for fast-forward).
3. Session boundary detection uses hard-coded NY hours (configurable in ReplayConfig).
4. Single-instrument, single-timeframe per session.
5. No real-time replay — offline historical only.
6. Engine callbacks are synchronous — blocking callbacks slow the entire pipeline.
