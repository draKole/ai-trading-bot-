# Confluence Engine — Design & Distribution

## Overview

The Confluence Engine aggregates outputs from all Phase 1 & 2 analysis engines into unified market-state snapshots. A configurable Rule Engine evaluates conditions against snapshots without making trade decisions — the engine describes market conditions, it doesn't prescribe actions.

## Architecture

```
Market Structure ─┐
Liquidity         ├── ConfluenceEngine ──→ ConfluenceSnapshot + RuleResults
FVG               │
Order Blocks      │
SMT Divergence    ┘
```

| Component | File | Purpose |
|-----------|------|---------|
| `ConfluenceConfig` | `engine.py` | 10 configurable parameters + rule list |
| `build_snapshot()` | `engine.py` | Aggregate all engine outputs into snapshot |
| `evaluate_rules()` | `engine.py` | Evaluate conditions with 4 operators |
| `ConfluenceService` | `service.py` | Persistence, queries, statistics |

---

## 1. Confluence Snapshot

A snapshot captures the market state at a single point in time:

| Section | Fields | Source Engine |
|---------|--------|---------------|
| **Identity** | instrument, timeframe, timestamp | — |
| **Trend** | trend, confidence | Market Structure |
| **Structure** | swing_direction, ms counts, latest BOS/CHoCH | Market Structure |
| **Liquidity** | sweep counts by direction | Liquidity Engine |
| **FVG** | active/mitigated counts by direction | FVG Engine |
| **Order Blocks** | active/mitigated counts by direction | Order Block Engine |
| **SMT** | active counts by direction | SMT Engine |
| **Session** | session name, alignment flag | Session Engine |
| **Aggregate** | weighted bullish/bearish signals, agreement ratio | Computed |

### Trend Determination

```
bullish:  ms_bullish_count > ms_bearish_count * 1.5
bearish:  ms_bearish_count > ms_bullish_count * 1.5
choppy:   mixed signals within 1.5x band
neutral:  no MS events
```

### Aggregate Signals

```
bullish_signals = Σ(engine_present * weight) for bullish engines
bearish_signals = Σ(engine_present * weight) for bearish engines
agreement_ratio = max(bullish, bearish) / total
trend_confidence = agreement_ratio * 100
```

---

## 2. Rule Engine

### Rule Definition

A Rule is a named collection of conditions with an evaluation operator:

```python
Rule(
    name="bullish_strong_confluence",
    description="Multiple bullish engines agree",
    conditions=[...],
    operator="minimum",      # all | any | majority | minimum
    min_matches=2,
    direction="bullish",
    group="confluence",
    weight=1.0,
)
```

### Condition Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `all` | ALL conditions must match | BOS + FVG + OB all present |
| `any` | ANY condition matches | At least one engine shows bullish |
| `majority` | >50% of conditions match | 2 out of 3 engines agree |
| `minimum` | At least N conditions match | 2 out of 4 engines agree |

### Condition Types

| Operator | Meaning |
|----------|---------|
| `gt` | Greater than |
| `gte` | Greater than or equal |
| `lt` | Less than |
| `lte` | Less than or equal |
| `eq` | Equal to (case-insensitive for strings) |
| `neq` | Not equal |
| `exists` | Non-null and non-zero |

### Field Aliases

Short aliases for snapshot fields:
- `ms.bullish_count` → `ms_bullish_count`
- `liq.sweeps` → `active_sweeps_count`
- `fvg.bullish` → `fvg_bullish_count`
- `ob.active` → `ob_active_count`
- `smt.bullish` → `smt_bullish_count`
- `swing_direction`, `trend`, `session_aligned`

### Default Rules

| Rule | Group | Direction |
|------|-------|-----------|
| `bullish_bos_plus_fvg` | structure | bullish |
| `bearish_bos_plus_fvg` | structure | bearish |
| `liquidity_sweep_plus_ob` | liquidity | neutral |
| `bullish_smt_present` | smt | bullish |
| `bearish_smt_present` | smt | bearish |
| `bullish_strong_confluence` | confluence | bullish (min 2 of 4) |
| `bearish_strong_confluence` | confluence | bearish (min 2 of 4) |

---

## 3. Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `time_window_seconds` | 3600 | Lookback window for active events |
| `min_evidence_sources` | 1 | Minimum engines required |
| `session_alignment_required` | False | Whether session affects evaluation |
| `trend_weight` | 1.0 | Market Structure weight in scoring |
| `liquidity_weight` | 1.0 | Liquidity weight |
| `fvg_weight` | 0.8 | FVG weight |
| `ob_weight` | 1.2 | Order Block weight |
| `smt_weight` | 1.5 | SMT weight (highest — cross-instrument) |
| `enabled_timeframes` | [] | Timeframes to analyze |
| `rules` | [] | Rule list for evaluation |

---

## 4. Database Schema

### `confluence_snapshots`
36 columns covering all engine counts, aggregate signals, config snapshot.

Indexes: instrument, timeframe, timestamp, composite (instrument, timeframe).

### `confluence_rule_results`
10 columns: snapshot_id, rule_name, matched, direction, match_count, score, evidence.

Indexes: snapshot_id, rule_name.

### `confluence_rules`
11 columns: name (unique), conditions_json, operator, group, weight, direction, enabled.

---

## 5. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/confluence/snapshot` | Build + store snapshot |
| `POST` | `/api/v1/confluence/snapshot-dry-run` | Dry-run evaluation |
| `GET` | `/api/v1/confluence/snapshots` | Historical snapshots |
| `GET` | `/api/v1/confluence/snapshots/{id}` | Single snapshot + rule results |
| `GET` | `/api/v1/confluence/rules` | Rule definitions |
| `GET` | `/api/v1/confluence/statistics` | Trend distribution |

---

## 6. Limitations

1. **Snapshot is a point-in-time aggregate** — doesn't track evolution between snapshots.
2. **No rule conflict resolution** — contradictory rules both report matched.
3. **Weighted scoring is additive** — assumes independence of signals; no correlation discount.
4. **No multi-timeframe confluence** — each timeframe produces independent snapshots.
5. **No historical replay yet** — snapshots are stored but backtesting integration TBD.
6. **No trend change detection** — doesn't flag when market state transitions.
