# SMT Divergence Engine — Mathematical Definitions

## Overview

The Smart Money Technique (SMT) Divergence Engine detects when two correlated instruments diverge at key Market Structure swing points, revealing potential smart money activity.

## Architecture

```
Market Structure Events (Instrument A) ──┐
                                          ├── SMT Detector → SMT Events (DB/API)
Market Structure Events (Instrument B) ──┘
                                          ↑
                                     SMTConfig
```

| Component | File | Purpose |
|-----------|------|---------|
| `SMTConfig` | `detector.py` | 7 configurable parameters + pair definitions |
| `detect_smt_divergence()` | `detector.py` | Cross-instrument swing comparison |
| `SMTService` | `service.py` | Persistence, queries, statistics |

---

## 1. Detection Rules

### Bearish SMT Divergence (HH Divergence)

**Condition**: Primary instrument makes a Higher High (HH), but secondary instrument fails to make a corresponding Higher High.

```
Primary:  swing_high[now] > swing_high[prior]     → HH
Secondary: swing_high[now] ≤ swing_high[prior]    → NOT HH (LH or equal)
→ BEARISH SMT
```

Interpretation: Smart money is distributing on the secondary instrument while the primary is pushed higher — distribution trap.

**Divergence %**: `(secondary_prior - secondary_now) / secondary_prior * 100`

Measures how much the secondary retraced while the primary made new highs.

### Bullish SMT Divergence (LL Divergence)

**Condition**: Primary instrument makes a Lower Low (LL), but secondary instrument fails to make a corresponding Lower Low.

```
Primary:  swing_low[now] < swing_low[prior]     → LL
Secondary: swing_low[now] ≥ swing_low[prior]    → NOT LL (HL or equal)
→ BULLISH SMT
```

Interpretation: Smart money is accumulating on the secondary instrument while the primary is pushed lower — accumulation trap.

**Divergence %**: `(secondary_now - secondary_prior) / secondary_prior * 100`

Measures how much the secondary held above while the primary made new lows.

---

## 2. Swing Matching

### Algorithm

For each swing point on the primary instrument:

1. Identify swing type (high or low)
2. Find the nearest swing of the same type on the secondary instrument
3. Verify timestamp is within `timestamp_tolerance_seconds`
4. Compare HH/LL status between both instruments
5. If one made a new extreme and the other didn't → SMT Divergence

### Matching Methods

| Method | Description |
|--------|-------------|
| `nearest_time` | Match closest swing in time (default) |

---

## 3. Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pairs` | [] | List of `{primary, secondary}` instrument pairs |
| `timestamp_tolerance_seconds` | 300 | Max seconds between matching swings |
| `matching_method` | "nearest_time" | Swing matching strategy |
| `comparison_window_bars` | 10 | Max bars window for matching |
| `require_prior_swings` | True | Need prior swings for HH/LL comparison |
| `min_divergence_pct` | 0.05 | Minimum % divergence to qualify |
| `enabled_timeframes` | ["5m","15m","1h"] | Timeframes to detect on |

---

## 4. Relationship Model

Each SMT event references:

| Field | Type | Source |
|-------|------|--------|
| `primary_ms_event_id` | Integer | Market Structure event on primary |
| `secondary_ms_event_id` | Integer | Market Structure event on secondary |
| `related_liquidity_ids` | JSON array | Liquidity events near divergence |
| `related_fvg_ids` | JSON array | FVGs near divergence |
| `related_ob_ids` | JSON array | Order Blocks near divergence |

---

## 5. Database Schema

### `smt_events`
28 columns tracking both instruments' swing data, divergence metrics, related entity references, and config snapshots.

Indexes: primary_instrument, secondary_instrument, timeframe, direction, detection_timestamp, composite (primary, secondary, timeframe).

### `smt_pair_configs`
8 columns for instrument pair configuration storage. Unique constraint on (primary, secondary).

Indexes: implicit via unique constraint.

---

## 6. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/smt/directions` | bullish/bearish |
| `GET` | `/api/v1/smt/pairs` | Supported pairs |
| `POST` | `/api/v1/smt/detect` | Run detection + persist |
| `POST` | `/api/v1/smt/detect-dry-run` | Dry-run detection |
| `GET` | `/api/v1/smt/events` | Query (filters: pair, tf, direction) |
| `GET` | `/api/v1/smt/latest` | Latest signals for a pair |
| `GET` | `/api/v1/smt/statistics` | Stats by direction/timeframe |

---

## 7. Limitations

1. **Pair-dependent**: Requires correlated instruments. SMT not applicable to unrelated instruments.
2. **Swing-based**: Depends on Market Structure Engine (Phase 1B) for swing detection quality.
3. **Nearest-time matching only**: Currently only supports nearest-time matching, not value-based.
4. **No multi-timeframe confluence**: Each timeframe analyzed independently.
5. **No confirmation delay**: SMT is flagged immediately when both swings are detected.
6. **Prior swing dependency**: With `require_prior_swings=True`, first swing of each type is never compared.
