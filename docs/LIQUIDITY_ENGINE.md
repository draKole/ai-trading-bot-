# Liquidity Engine — Mathematical Definitions

## Overview

The Liquidity Engine integrates with the Market Structure Engine (Phase 1B) to detect, track, and classify liquidity levels and price interactions. All definitions are deterministic — no subjective interpretation.

## Architecture

```
OHLCV Bars + Swing Points → LiquidityEngine → Levels + Events (DB/API)
         ↓                          ↓
   SessionEngine              LiquidityConfig
   (timezone-aware)           (all parameters)
```

| Component | File | Purpose |
|-----------|------|---------|
| `SessionConfig` / `SessionEngine` | `session_engine.py` | Timezone-aware session boundary detection |
| `LiquidityConfig` | `engine.py` | All configurable thresholds |
| `LiquidityEngine.detect_levels()` | `engine.py` | Level detection (PDH, sessions, equals, swings, internal) |
| `LiquidityEngine.detect_events()` | `engine.py` | Event classification (approached, touched, swept, rejected, broken) |
| `LiquidityService` | `service.py` | Database persistence and query |

---

## 1. Session Engine

### Sessions
Four trading sessions are defined in US Eastern time (configurable):

| Session | ET Times | Description |
|---------|----------|-------------|
| Asia | 20:00–02:00 | Tokyo session (overnight, wraps past midnight) |
| London | 03:00–11:00 | European session |
| NY AM | 09:30–12:00 | New York morning |
| NY PM | 12:00–16:00 | New York afternoon |

### Overlap Resolution
When sessions overlap (e.g., London + NY AM 09:30–11:00 ET), the **later-starting** session takes priority. A bar at 10:30 ET is classified as NY AM, not London.

### Timezone & DST
- Default timezone: `America/New_York`
- Fully configurable via `SessionConfig.timezone`
- Uses Python's `zoneinfo` for DST-aware conversions
- All internal comparisons use UTC

### Session Boundary
For a session with start time `S` and end time `E`:
- If `S ≤ E`: same-day session
- If `S > E`: overnight session (end is next calendar day)

A bar is in session if its local time `t` satisfies `S ≤ t < E` (or `t ≥ S OR t < E` for overnight).

---

## 2. Liquidity Level Types

### 2.1 Previous Period Levels

**Previous Day High (PDH)**: `max(high)` of all bars whose date = previous calendar day.

**Previous Day Low (PDL)**: `min(low)` of all bars whose date = previous calendar day.

**PWH / PWL**: Same as above for the previous ISO week (Monday–Sunday).

**PMH / PML**: Same for the previous calendar month.

### 2.2 Session Levels

For each session, the **session high** is `max(high)` of all bars belonging to that session. The **session low** is `min(low)`.

NY AM and NY PM share the same level types (`ny_high` / `ny_low`) but are tracked separately.

### 2.3 Equal Highs / Equal Lows

**Equal Highs**: Two or more swing highs where:

```
|price_i - price_j| / price_i ≤ equal_level_tolerance_pct / 100
```

The average price of the cluster is used as the level.

**Equal Lows**: Same for swing lows.

Clusters require at least `equal_level_min_bars` bars between consecutive members.

### 2.4 Swing Liquidity

Liquidity resting **above** each swing high and **below** each swing low. These are natural targets for stop hunts.

- `swing_high_liq`: Price = swing high price. Liquidity above (stops).
- `swing_low_liq`: Price = swing low price. Liquidity below (stops).

### 2.5 Internal Liquidity

Mid-range levels derived from recent swing structure:
- `internal_high`: Most recent swing high (within last 3)
- `internal_low`: Most recent swing low (within last 3)

---

## 3. Liquidity Event Types

For each bar, check all active liquidity levels:

### 3.1 Approached
```
min(|bar_high - price|, |bar_low - price|) / price ≤ approach_threshold_pct / 100
```
AND bar does not touch the level.

### 3.2 Touched
```
bar_low ≤ price ≤ bar_high
```
Regular price interaction with no special characteristics.

### 3.3 Swept
**Bullish sweep**: Body below level, wick extends significantly below, body stays below.
```
max(open, close) < price AND price - bar_low > sweep_wick_pct/100 * price
```

**Bearish sweep**: Body above level, wick above, body stays above.
```
min(open, close) > price AND bar_high - price > sweep_wick_pct/100 * price
```

Each level can only be swept once (deduplication).

### 3.4 Rejected
**Bearish rejection**: Opens above level, closes below with strong momentum.
```
open > price AND close < price AND (price - close) / price ≥ rejection_reversal_pct / 100
```

**Bullish rejection**: Opens below level, closes above with strong momentum.
```
open < price AND close > price AND (close - price) / price ≥ rejection_reversal_pct / 100
```

### 3.5 Broken
Price closes completely beyond the level:
```
Bullish break: close > price AND low > price
Bearish break: close < price AND high < price
```
Requires `break_requires_close = True`.

---

## 4. Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `equal_level_tolerance_pct` | 0.05 | Max % difference for equal highs/lows |
| `equal_level_min_bars` | 3 | Min bars between equal cluster members |
| `approach_threshold_pct` | 0.1 | Distance % to trigger "approached" |
| `sweep_wick_pct` | 0.02 | Min wick % beyond level for sweep |
| `break_requires_close` | True | Whether "broken" needs close confirmation |
| `rejection_reversal_pct` | 0.15 | Min reversal % for rejection |
| `lookback_bars` | 5000 | Max bars to scan for PD/PS levels |
| `session_config` | See session | Session engine config |

---

## 5. Database Schema

### `liquidity_levels`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| instrument_id | Integer | FK to instruments |
| timeframe | String(10) | Bar timeframe |
| level_type | String(30) | One of 18 LiquidityType values |
| price | Float | Level price |
| source_bar_index | Integer | Bar that defined the level |
| source_timestamp | DateTime(tz) | When defined |
| session | String(20) | Session name (nullable) |
| is_active | Boolean | Active flag for invalidation |
| metadata_json | JSON | Additional info |
| config_snapshot | JSON | Config at detection time |

### `liquidity_events`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| instrument_id | Integer | FK to instruments |
| timeframe | String(10) | Bar timeframe |
| event_type | String(20) | approached/touched/swept/rejected/broken |
| level_type | String(30) | Type of level interacted with |
| level_price | Float | Price of the level |
| bar_index | Integer | Which bar triggered |
| bar_timestamp | DateTime(tz) | Timestamp |
| bar_high/low/close | Float | Bar OHLC for auditability |
| direction | String(10) | bullish/bearish |
| distance_pct | Float | Distance from level |

---

## 6. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/liquidity/event-types` | List all level + event types |
| `POST` | `/api/v1/liquidity/detect` | Run detection + persist |
| `POST` | `/api/v1/liquidity/detect-dry-run` | Dry-run detection |
| `GET` | `/api/v1/liquidity/levels` | Query active levels |
| `GET` | `/api/v1/liquidity/events` | Query historical events |
| `GET` | `/api/v1/liquidity/sweeps` | Query sweeps specifically |
| `GET` | `/api/v1/liquidity/session-status` | Session liquidity status |
| `GET` | `/api/v1/liquidity/session-history` | Session boundaries |

---

## 7. Limitations

1. **PD/PS levels**: Require at least one full bar in the previous period. Empty periods produce no levels.
2. **Session overlap**: London/NY AM overlap is resolved to NY AM. No dual-session tracking.
3. **Equal levels clustering**: Simple greedy clustering — not exhaustive. Different orderings may produce slightly different clusters.
4. **No volume-based liquidity**: Purely price-based. Order book depth, delta, CVD are not considered.
5. **Single timeframe**: Levels are tracked per-timeframe independently.
6. **No automatic invalidation**: `is_active` flag exists but automatic invalidation (e.g., level broken) is deferred to a future phase.
7. **Previous period computation**: Simple calendar-based (not trading-day aware for holidays).
