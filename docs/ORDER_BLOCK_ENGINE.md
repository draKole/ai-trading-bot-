# Order Block Engine — Mathematical Definitions

## Overview

The Order Block (OB) Engine identifies significant candles that precede strong directional moves confirmed by Market Structure breaks (BOS/CHoCH). Each OB is traceable to its originating Market Structure event and tracks a full lifecycle from creation through mitigation or invalidation.

## Architecture

```
Market Structure Events (BOS/CHoCH) ─────────┐
                                              ▼
OHLCV Bars → OB Detector (lookback search) → OrderBlock + Lifecycle Events (DB/API)
                    ↓                              ↓
               OBConfig                        OBConfig
```

| Component | File | Purpose |
|-----------|------|---------|
| `OBConfig` | `detector.py` | 10 configurable parameters |
| `detect_order_blocks()` | `detector.py` | BOS/CHoCH-triggered candle selection |
| `apply_ob_lifecycle()` | `detector.py` | Creation → touch → partial → mitigated → invalidated |
| `OrderBlockService` | `service.py` | Persistence, queries, statistics |

---

## 1. Detection Rules

### Trigger

An Order Block is ONLY created when a BOS, CHoCH, or MSS event is present in the Market Structure Engine output.

### Bullish Order Block

From a **bullish BOS/CHoCH** (price breaks above a previous swing high):
- Look back from the event bar within `lookback_bars`
- Find the **last bearish candle** (close < open)
- The OB bounds represent the sell-side liquidity that was absorbed:

**Default bounds** (`use_open_close_bounds=False`):
- Upper bound = `high` of the bearish candle
- Lower bound = `open` of the bearish candle

**Open/Close bounds** (`use_open_close_bounds=True`):
- Upper bound = `max(open, close)`
- Lower bound = `min(open, close)`

### Bearish Order Block

From a **bearish BOS/CHoCH** (price breaks below a previous swing low):
- Look back from the event bar within `lookback_bars`
- Find the **last bullish candle** (close > open)
- The OB bounds represent the buy-side liquidity that was absorbed:

**Default bounds** (`use_open_close_bounds=False`):
- Upper bound = `open` of the bullish candle
- Lower bound = `low` of the bullish candle

### Filters

A qualifying candle must pass:
1. Direction check: bearish candle for bullish OB, bullish candle for bearish OB
2. `min_body_size_pct`: Body as % of total range ≥ threshold (0.0 = no filter)
3. `max_block_size_pct`: Block size as % of midpoint ≤ threshold (5.0 default)
4. Duplicate prevention: `(direction, origin_candle_index)` dedup key

---

## 2. Lifecycle States

```
CREATED → first_touch → TOUCHED → mit≥30% → PARTIALLY_MITIGATED → mit≥threshold → MITIGATED
                                           ↘ price extends beyond → INVALIDATED
                                           ↘ max age exceeded → INVALIDATED
```

### Mitigation Percentage

**Bullish OB** (price fills by moving DOWN through the block):
```
mit% = (upper_bound - price) / block_size * 100
```
Where `price` = bar close (`mitigation_method="close"`) or bar low (`"wick"`).

**Bearish OB** (price fills by moving UP through the block):
```
mit% = (price - lower_bound) / block_size * 100
```
Where `price` = bar close or bar high.

Mitigation % is capped at [0, 100] and only increases (monotonic max).

### State Transitions

| From | To | Condition |
|------|----|-----------|
| active | touched | `mit% > 0` |
| touched | partially_mitigated | `mit% ≥ 30%` |
| partially_mitigated | mitigated | `mit% ≥ mitigation_threshold_pct` |
| any | invalidated | bullish: `close > upper_bound * (1 + invalidation_pct/100)` |
| any | invalidated | bearish: `close < lower_bound * (1 - invalidation_pct/100)` |
| any | invalidated | `bars_since_creation > expiration_bars` (if > 0) |

---

## 3. Lifecycle Events

| Event | Trigger |
|-------|---------|
| `created` | OB detected at BOS/CHoCH confirmation bar |
| `first_touch` | First bar where mit% > 0 |
| `partially_mitigated` | mit% reaches 30% |
| `mitigated` | mit% reaches threshold (default 100%) |
| `invalidated` | Price extends beyond or expires |

---

## 4. Relationship Model

Each Order Block references:

| Field | Type | Source |
|-------|------|--------|
| `related_ms_event_id` | Integer (nullable) | Market Structure Event ID |
| `related_liquidity_ids` | JSON array | Liquidity Level/Event IDs |
| `related_fvg_ids` | JSON array | Fair Value Gap IDs |

These are stored as nullable references — populated when related entities exist in the same instrument/timeframe context.

---

## 5. Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `lookback_bars` | 5 | Max candles to look back from BOS/CHoCH |
| `require_bos_choch` | True | Require BOS/CHoCH for OB creation |
| `use_open_close_bounds` | False | Use [open,close] instead of [high/low,open] |
| `min_body_size_pct` | 0.0 | Minimum candle body as % of range |
| `max_block_size_pct` | 5.0 | Maximum block size as % of price |
| `mitigation_method` | "close" | "close" or "wick" for fill calculation |
| `mitigation_threshold_pct` | 100.0 | % of OB range for full mitigation |
| `invalidation_pct` | 0.5 | % beyond OB to trigger invalidation |
| `expiration_bars` | 0 | Max bars before auto-invalidation (0=never) |
| `enabled_timeframes` | [] | Timeframes to detect on (empty=all) |

---

## 6. Database Schema

### `order_blocks`
30 columns including: direction, status, bounds, midpoint, block_size, block_size_pct, mitigation_percentage, origin/creation timestamps, related entity IDs (ms_event, liquidity_ids, fvg_ids), 5 origin candle fields, config_snapshot.

Indexes: instrument_id, timeframe, direction, status, creation_timestamp, composite (instrument_id, timeframe, direction, status).

### `ob_lifecycle_events`
12 columns including: ob_id, event_type, bar_index, mitigation_percentage.

Indexes: ob_id, instrument_id, event_type.

---

## 7. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/order-blocks/directions` | bullish/bearish |
| `GET` | `/api/v1/order-blocks/statuses` | All status values |
| `POST` | `/api/v1/order-blocks/detect` | Run detection + persist |
| `POST` | `/api/v1/order-blocks/detect-dry-run` | Dry-run detection |
| `GET` | `/api/v1/order-blocks/active` | Query (filters: tf, direction, status) |
| `GET` | `/api/v1/order-blocks/events` | Lifecycle events |
| `GET` | `/api/v1/order-blocks/statistics` | Stats by timeframe |

---

## 8. Limitations

1. **BOS/CHoCH dependency**: OBs require Market Structure events. Without prior Phase 1B detection, no OBs are created.
2. **Single-candle OB**: Only one candle is selected per BOS/CHoCH. Multi-candle block structures are not supported.
3. **Linear lookback**: Searches sequentially from the event bar. Does not consider market context beyond the lookback window.
4. **No confluence scoring**: Related liquidity/FVG references are stored but not scored.
5. **Mitigation is monotonic**: Once mitigated, an OB cannot be reactivated.
6. **No mitigation retest tracking**: Does not track whether price returns to the OB zone after mitigation.
