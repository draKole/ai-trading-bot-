# FVG Engine — Mathematical Definitions

## Overview

The Fair Value Gap (FVG) Engine detects 3-candle price imbalance patterns, tracks their lifecycle from creation through mitigation or invalidation, and persists every state transition for auditability.

## Architecture

```
OHLCV Bars → FVG Detector (3-candle) → Lifecycle Manager → FVGs + Events (DB/API)
                    ↓                           ↓
              FVGConfig                    FVGConfig
```

| Component | File | Purpose |
|-----------|------|---------|
| `FVGConfig` | `detector.py` | All configurable parameters |
| `detect_fvgs()` | `detector.py` | 3-candle pattern detection |
| `apply_lifecycle()` | `detector.py` | Creation → touch → fill → mitigation → invalidation |
| `FVGService` | `service.py` | Database persistence, queries, statistics |

---

## 1. FVG Detection

### 3-Candle Pattern

For any three consecutive candles indexed 0, 1, 2:

**Bullish FVG**: `low[2] > high[0]`
- Lower bound = `high[0]`
- Upper bound = `low[2]`
- Gap size = `low[2] - high[0]`
- Midpoint = `(high[0] + low[2]) / 2`

**Bearish FVG**: `high[2] < low[0]`
- Upper bound = `low[0]`
- Lower bound = `high[2]`
- Gap size = `low[0] - high[2]`
- Midpoint = `(low[0] + high[2]) / 2`

### Filters

An FVG is only created if:
1. `gap_size > 0` (bounds don't touch)
2. `gap_size ≥ min_gap_size` (absolute minimum)
3. `gap_size / midpoint * 100 ≥ min_gap_size_pct` (relative minimum)
4. Timeframe is in `enabled_timeframes` (if specified)

---

## 2. Lifecycle States

```
CREATED → first_touch → PARTIALLY_FILLED → fully filled → MITIGATED
                                                  ↘ price extends → INVALIDATED
                                                  ↘ max age exceeded → INVALIDATED
```

### Fill Percentage

**Bullish FVG** (price fills by moving DOWN):
```
fill% = (upper_bound - price) / gap_size * 100
```
Where `price` = bar close (if `use_close_for_fill=True`) or bar low (if `False`).

**Bearish FVG** (price fills by moving UP):
```
fill% = (price - lower_bound) / gap_size * 100
```
Where `price` = bar close or bar high.

Fill % is capped at [0, 100] and only increases (monotonic max).

### State Transitions

| From | To | Condition |
|------|----|-----------|
| active | partially_filled | `fill% > 0` |
| partially_filled | mitigated | `fill% ≥ 100 - fill_tolerance_pct` |
| any | invalidated | bullish: `close > upper_bound * (1 + invalidation_pct/100)` |
| any | invalidated | bearish: `close < lower_bound * (1 - invalidation_pct/100)` |
| any | invalidated | `bars_since_creation > max_age_bars` (if max_age_bars > 0) |

---

## 3. Lifecycle Events

For each state transition, an event is emitted:

| Event | Trigger |
|-------|---------|
| `created` | FVG detected on candle 3 close |
| `first_touch` | First bar where fill% > 0 |
| `partial_fill` | Fill increases by ≥10% (significant change) |
| `mitigated` | Fill reaches 100% - tolerance |
| `invalidated` | Price extends beyond gap or max age exceeded |

---

## 4. Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_gap_size` | 0.0 | Minimum absolute gap in price units |
| `min_gap_size_pct` | 0.01 | Minimum gap as % of midpoint |
| `fill_tolerance_pct` | 1.0 | Tolerance for "fully mitigated" |
| `use_close_for_fill` | False | True = use close; False = use wicks |
| `invalidation_pct` | 0.5 | % beyond gap to trigger invalidation |
| `max_age_bars` | 0 | Max bars before auto-invalidation (0=never) |
| `enabled_timeframes` | [] | Timeframes to detect on (empty=all) |

---

## 5. Database Schema

### `fair_value_gaps`
26 columns including: direction, status, bounds, midpoint, gap_size, gap_size_pct, fill_percentage, creation/mitigation/invalidation timestamps, 6 candle audit fields, config_snapshot.

Indexes: instrument_id, timeframe, direction, status, creation_timestamp, composite (instrument_id, timeframe, direction, status).

### `fvg_lifecycle_events`
13 columns including: fvg_id, event_type, bar_index, fill_percentage, fvg_direction, fvg_upper/lower.

Indexes: fvg_id, instrument_id, event_type.

---

## 6. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/fvg/directions` | List direction values |
| `GET` | `/api/v1/fvg/statuses` | List status values |
| `POST` | `/api/v1/fvg/detect` | Run detection + persist |
| `POST` | `/api/v1/fvg/detect-dry-run` | Dry-run detection |
| `GET` | `/api/v1/fvg/active` | Query FVGs (filters: tf, direction, status) |
| `GET` | `/api/v1/fvg/events` | Query lifecycle events |
| `GET` | `/api/v1/fvg/statistics` | Stats grouped by timeframe |

---

## 7. Limitations

1. **Single-timeframe**: Each timeframe analyzed independently. No multi-timeframe FVG confluence.
2. **Greedy detection**: Every 3-candle window is checked. No deduplication of overlapping FVGs from the same impulse.
3. **No OTE/retracement tracking**: Only gap creation and fill — no optimal trade entry tracking.
4. **Fill is monotonic**: Fill % only increases; once mitigated, an FVG cannot become active again.
5. **No volume confirmation**: Purely price-based pattern detection.
6. **Invalidation is one-way**: Once invalidated, never reactivated.
