# Market Structure Engine — Mathematical Definitions

## Overview

The Market Structure Engine consumes normalized OHLCV bars and produces deterministic, auditable market structure events. All definitions are mathematical — no subjective interpretation, no AI, no ML.

## Architecture

```
OHLCV Bars → Swing Detector → Structure Analyzer → Events (DB/API)
                  ↓                    ↓
              Config             Config (to_dict)
```

### Components

| Component | File | Purpose |
|-----------|------|---------|
| `MarketStructureConfig` | `config.py` | All configurable parameters with defaults |
| `detect_swings()` | `swing_detector.py` | Pure-function swing point detection |
| `analyze_structure()` | `structure_analyzer.py` | HH/HL/LH/LL/BOS/CHoCH/MSS classification |
| `MarketStructureEngine` | `engine.py` | Orchestrator — wires swing detection + analysis |
| `MarketStructureService` | `service.py` | Database persistence and query layer |

---

## 1. Swing Point Detection

### Swing High

A bar at index `i` is a **Swing High** if and only if:

```
high[i] > high[j]  for all j ∈ [i - L, i + L], j ≠ i
```

where `L` = `swing_lookback`.

A swing high is **confirmed** when `i + C < N`, where `C` = `swing_confirmation_bars` and `N` is the total number of bars. Confirmation prevents repainting — a swing at the very end of the data cannot be confirmed.

### Swing Low

A bar at index `i` is a **Swing Low** if and only if:

```
low[i] < low[j]  for all j ∈ [i - L, i + L], j ≠ i
```

### Filters

1. **Confirmation delay**: Only swings with at least `C` bars after them are kept.
2. **Minimum distance**: Two swing highs must be separated by at least `min_structure_distance_bars` bars. Same for swing lows.
3. **Minimum swing size**: If `min_swing_size_pct > 0`, a swing must have `|high[i] - low[i]| / avg_price * 100 ≥ min_swing_size_pct`.

---

## 2. Structure Classification (HH / HL / LH / LL)

After swing points are detected in chronological order:

### Higher High (HH)
A swing high where `price > previous_swing_high.price`.

### Lower High (LH)
A swing high where `price < previous_swing_high.price`.

### Higher Low (HL)
A swing low where `price > previous_swing_low.price`.

### Lower Low (LL)
A swing low where `price < previous_swing_low.price`.

The **first** swing high in a series is classified as `swing_high` (not HH or LH) because there is no prior reference. Same for the first swing low.

---

## 3. Trend Determination

Trend is determined by comparing counts of structural moves:

```
bullish_score = count(HH) + count(HL)
bearish_score = count(LH) + count(LL)
```

- `bullish_score > bearish_score` → **bullish**
- `bearish_score > bullish_score` → **bearish**
- Equal → last swing direction breaks tie; otherwise **neutral**

---

## 4. Break of Structure (BOS)

### Bullish BOS
When price **breaks above** a prior swing high **in a bullish trend**.

Conditions:
1. Trend is **bullish**.
2. A bar's high (or body, if `use_body_for_breaks=True`) exceeds a prior swing high's price.
3. If `bos_requires_close=True`, the bar's close must also exceed the level.
4. Each swing high level can only trigger one BOS (deduplication).

### Bearish BOS
When price **breaks below** a prior swing low **in a bearish trend**.

Conditions mirror the above, with price breaking below a prior swing low.

---

## 5. Change of Character (CHoCH)

### Bullish CHoCH
When price **breaks above** a prior swing high **in a bearish trend**.

This signals a potential trend reversal.

### Bearish CHoCH
When price **breaks below** a prior swing low **in a bullish trend**.

### CHoCH vs. BOS
The distinction is purely trend-dependent:
- **BOS** = break in the direction of the trend (continuation).
- **CHoCH** = break against the trend (potential reversal).

---

## 6. Market Structure Shift (MSS)

An **MSS** is a stronger variant of CHoCH:

- A CHoCH where the bar **closes** beyond the broken level (if `choch_requires_close=True`).
- If `mss_requires_retest=True`, additionally requires a subsequent retest of the broken level after the break.

In the default configuration (`choch_requires_close=True`), a CHoCH with a close beyond the level is automatically classified as MSS.

---

## 7. Configuration

All parameters are defined in `MarketStructureConfig`:

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `swing_lookback` | 5 | 2–50 | Bars left/right to confirm swing |
| `swing_confirmation_bars` | 1 | 0–10 | Bars after swing before confirming |
| `min_structure_distance_bars` | 3 | 1–20 | Minimum bars between same-type swings |
| `bos_requires_close` | True | bool | BOS needs close beyond level |
| `choch_requires_close` | True | bool | CHoCH needs close beyond level |
| `mss_requires_retest` | False | bool | MSS needs retest of broken level |
| `use_body_for_breaks` | False | bool | Use candle body instead of wicks |
| `min_swing_size_pct` | 0.0 | float | Minimum swing size as % of price |

Configuration is serialized into every stored event for auditability.

---

## 8. Database Schema

Table: `market_structure_events`

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer PK | Auto-increment |
| `instrument_id` | Integer FK | References `instruments.id` |
| `timeframe` | String(10) | e.g. "5m", "1h" |
| `bar_timestamp` | DateTime(tz) | Timestamp of the bar |
| `event_type` | String(20) | One of: swing_high, swing_low, higher_high, higher_low, lower_high, lower_low, bos, choch, mss |
| `price_level` | Float | Price at which the event occurred |
| `direction` | String(10) | "bullish" or "bearish" |
| `parent_swing_id` | Integer FK | Self-reference to parent swing event |
| `confirmed_at` | DateTime(tz) | When the swing was confirmed |
| `config_snapshot` | JSON | Full config that produced this event |
| `metadata_json` | JSON | Additional metadata (break bar index, etc.) |
| `schema_version` | String(10) | For forward compatibility |
| `created_at` | DateTime(tz) | Record creation time |

Indexes: `(instrument_id)`, `(timeframe)`, `(bar_timestamp)`, `(event_type)`, `(instrument_id, timeframe, event_type)`.

---

## 9. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/market-structure/event-types` | List all event types |
| `POST` | `/api/v1/market-structure/detect` | Run detection on stored bars, persist |
| `POST` | `/api/v1/market-structure/detect-dry-run` | Run detection, return events without storing |
| `GET` | `/api/v1/market-structure/events` | Query stored events (filters: instrument, tf, type, date range) |
| `GET` | `/api/v1/market-structure/latest` | Latest swing high, low, and break |

---

## 10. Limitations

1. **Endpoint bias**: Swings at the extreme edges of the bar series are not detected (need `lookback` bars on both sides).
2. **Single-break detection**: Only the first break of each swing level is recorded. Multiple breaks of the same level are not tracked.
3. **Trend determination**: Uses simple HH/HL/LH/LL counting. Does not consider magnitude or duration.
4. **No multi-timeframe analysis**: Each timeframe is analyzed independently. Higher-timeframe structure does not influence lower-timeframe analysis.
5. **No volume or delta**: Purely price-based — does not incorporate volume, delta, or order flow.
6. **MSS retest not implemented**: The `mss_requires_retest=True` config exists but the retest detection logic is deferred to a future phase.
