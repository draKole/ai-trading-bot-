# Trade Management Engine — Lifecycle State Machine

## Overview

The Trade Management Engine manages the lifecycle of an approved trade after entry. It consumes Trade Setup + Risk Report + Position Recommendation + market bars to track state transitions, stop movements, target hits, and exits. Advisory only — no broker communication.

## Architecture

```
TradeSetup + RiskReport + PositionRec + Bars → TradeManager
                                                   ↓
                                              ManagedTrade (stateful)
                                                   ↓
                                              process_bar() per bar
                                                   ↓
                                              Events: stop_update, target_hit, exit
```

---

## 1. State Machine — 12 States

```
pending_entry → entered → active
                  ↓          ↓
            partially_filled  → target_1_hit
                                  ↓
                               target_2_hit
                                  ↓
                               target_3_hit → exited

active → stop_moved_to_breakeven
active → trailing_stop_active(→trailing moves)

any → cancelled / expired
```

### State Transitions (per bar)

| Condition | From | To |
|-----------|------|-----|
| Bar hits stop | active/* | exited |
| Bar hits T1 | active/* | target_1_hit |
| Bar hits T2 | * | target_2_hit |
| Bar hits T3 (no partials) | target_2_hit | exited |
| R ≥ breakeven_trigger_r | active | stop_moved_to_breakeven |
| R ≥ trailing_activate_r | active | trailing_stop_active |
| Duration > max | active | exited |
| Manual cancel | any pending/active | cancelled |
| Never entered | pending_entry | expired |

Priority: stop loss > breakeven > trailing > targets (bar evaluation order). Targets override breakeven/trailing state.

---

## 2. Trade Event Model

Every state transition generates an immutable `TradeEvent`:

| Field | Description |
|-------|-------------|
| `event_id` | UUID |
| `trade_id` | Parent trade |
| `event_type` | state_change, stop_update, target_hit, exit, trailing_activate, partial_exit |
| `from_state` / `to_state` | Transition |
| `price` | Trigger price |
| `r_multiple` | Current R |
| `position_remaining_pct` | After partial exits |

---

## 3. Management Rules (configurable)

| Rule | Default | Description |
|------|---------|-------------|
| `breakeven_trigger_r` | 1.0 | Move stop to entry at 1R profit |
| `breakeven_enabled` | True | |
| `trailing_activate_r` | 1.5 | Activate trailing at 1.5R |
| `trailing_distance_pct` | 0.5% | Trail distance as % of price |
| `trailing_enabled` | True | |
| `partial_exit_pct` | 33% | Close % at each target |
| `partial_exit_enabled` | False | |
| `max_trade_duration_minutes` | None | Time exit |
| `time_exit_enabled` | False | |
| `exit_on_session_close` | False | Exit at session end |
| `gap_skip_stops` | True | Don't trigger on gaps |

---

## 4. Tracked Metrics

| Metric | Description |
|--------|-------------|
| `current_r` | (price - entry) / risk_r |
| `peak_r` | Max favorable R (MFE) |
| `max_adverse_r` | Max adverse R (MAE) |
| `position_remaining` | After partial exits |
| `breakeven_reached` | Flag |
| `trailing_active` | Flag |
| `target_N_hit` | Flags |

---

## 5. Database Schema

### `managed_trades` — 25 columns
trade_id (unique), setup_id, instrument, direction, entry/stop prices, position_size/remaining, T1/T2/T3 + hit flags, state, R metrics, breakeven/trailing flags.

Indexes: trade_id, setup_id, instrument, state.

### `trade_events` — 10 columns
trade_id, event_type, from_state, to_state, detail, price, r_multiple, position_remaining_pct.

Index: trade_id.

### `trade_management_rules` — 8 columns
name (unique), description, rule_type, threshold, group, priority, enabled.

---

## 6. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/trade-management/trades` | List trades |
| `GET` | `/api/v1/trade-management/trades/{id}` | Single trade + events |
| `GET` | `/api/v1/trade-management/events` | List events |
| `POST` | `/api/v1/trade-management/manage-dry-run` | Simulate bar-by-bar |
| `GET` | `/api/v1/trade-management/statistics` | Distribution stats |

---

## 7. Limitations

1. No broker communication — advisory only
2. Session close exit is a placeholder
3. Gap handling is config-dependent
4. Single trade management — no portfolio coordination
5. Time exit uses bar timestamp, not wall clock
