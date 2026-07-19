# Strategy Engine — Market Bias + Trade Setup Generator

## Overview

The Strategy Engine consumes Confluence Engine output to produce standardized Market Bias assessments and advisory Trade Setup objects. It answers: **"Given the current market state, is there a valid trade setup?"** — without executing orders.

## Architecture

```
ConfluenceSnapshot → MarketBiasEngine → StrategyRuleEngine
                                              ↓
                                       TradeSetupGenerator
                                              ↓
                                        TradeSetup (advisory)
```

| Component | File | Purpose |
|-----------|------|---------|
| `MarketBias` | `engine.py` | Directional bias with strength, confidence, grade |
| `TradeSetup` | `engine.py` | Entry zone, targets, stop reference — advisory only |
| `StrategyRule` | `engine.py` | Configurable rule definitions |
| `build_market_bias()` | `engine.py` | Score all engines into directional bias |
| `generate_trade_setup()` | `engine.py` | Produce entry/stop/target from bias + evidence |
| `evaluate_strategy_rules()` | `engine.py` | Evaluate rules against setups |
| `StrategyService` | `service.py` | DB persistence, queries, statistics |

---

## 1. Market Bias Model

| Field | Type | Description |
|-------|------|-------------|
| `instrument` | str | e.g., "ES" |
| `timeframe` | str | e.g., "5m" |
| `direction` | str | bullish, bearish, neutral |
| `strength_score` | float | 0-100 |
| `confidence` | str | Very Low → Very High |
| `trend` | str | From confluence |
| `market_regime` | str | trending, ranging, choppy, breakout |
| `bias_grade` | str | A+ through F |
| `supporting_evidence` | list[dict] | Source engines + IDs |
| `contradicting_evidence` | list[dict] | Opposite signals |

### Scoring Weights (configurable)

| Engine | Default Weight | Max Points |
|--------|---------------|------------|
| Market Structure | 25 | 25 |
| FVG Alignment | 20 | 20 |
| Order Block | 20 | 20 |
| SMT Confirmation | 20 | 20 |
| Liquidity Sweep | 10 | 10 |
| Session Alignment | 5 | 5 |
| **Total** | | **100** |

### Grade Scale

| Score | Grade | Confidence |
|-------|-------|------------|
| 95+ | A+ | Very High |
| 90-94 | A | High |
| 85-89 | A- | High |
| 80-84 | B+ | High |
| 75-79 | B | High |
| 70-74 | B- | High |
| 65-69 | C+ | Medium |
| 60-64 | C | Medium |
| 55-59 | C- | Medium |
| 50-54 | D | Low |
| <50 | F | Very Low |

---

## 2. Trade Setup Model

| Field | Type | Description |
|-------|------|-------------|
| `setup_id` | UUID | Unique identifier |
| `direction` | str | bullish, bearish |
| `status` | str | pending, ready, waiting_confirmation, expired, cancelled |
| `entry_zone_low` | float | Lower bound of entry zone |
| `entry_zone_high` | float | Upper bound |
| `preferred_entry` | float | Midpoint of zone |
| `stop_reference` | float | Where stop would be placed |
| `target_1` | float | First target |
| `target_2` | float \| None | Second target |
| `target_3` | float \| None | Third target |
| `required_confirmation` | list[str] | Missing pieces needed |
| `setup_score` | float | 0-100 |
| `setup_grade` | str | A+ through F |
| `expires_at` | datetime | Auto-expiry |

### Entry Zone Derivation

- **Source**: Best active Order Block matching bias direction
- **Zone**: [OB low, OB high] from the block's price bounds
- Preferred entry = midpoint

### Stop Reference

- **Bullish**: Lowest swing low minus `stop_buffer_pct`
- **Bearish**: Highest swing high plus `stop_buffer_pct`

### Targets

- **Source 1**: Far side of aligned active FVGs
- **Source 2**: Active liquidity levels beyond entry

---

## 3. Strategy Rules

| Rule | Group | Direction | Required | Optional |
|------|-------|-----------|----------|----------|
| `bullish_high_confidence` | high_confidence | bullish | direction=bullish, has_entry_zone, has_stop | has_targets, status=ready |
| `bearish_high_confidence` | high_confidence | bearish | direction=bearish, has_entry_zone, has_stop | has_targets, status=ready |
| `pending_setup` | monitoring | neutral | status=pending/waiting_confirmation | — |

### Rule Operators

- **Required conditions**: ALL must match (`require_all_required=True`)
- **Optional conditions**: At least `min_optional_count` (default 2)
- **Score threshold**: Setup score ≥ `min_score` (default 60)

---

## 4. Setup Lifecycle

```
pending → ready ──────────→ (future: executed)
    ↓        ↓
waiting_confirmation   expired
```

- **pending**: Score below `min_setup_score`
- **ready**: All required conditions met, score above threshold
- **waiting_confirmation**: Missing OB entry zone or stop reference
- **expired**: Auto after `setup_expiry_minutes`
- **cancelled**: Manual cancellation

No `executed` status — execution belongs to future phase.

---

## 5. Database Schema

### `market_biases`
17 columns: direction, strength_score, confidence, trend, regime, session, bias_grade, evidence JSON.

Indexes: setup_id, instrument, timeframe, timestamp.

### `trade_setups`
23 columns: setup_id (unique), direction, status, entry zone, stop, targets, evidence, config snapshot.

Indexes: setup_id, instrument, timeframe, status.

### `strategy_rules`
11 columns: name (unique), direction, required/optional conditions JSON, min_score, priority, enabled.

### `strategy_evaluations`
12 columns: setup_id, rule_name, passed, condition counts, scores.

Indexes: setup_id, rule_name.

---

## 6. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/strategy/evaluate` | Full pipeline: bias → setup → rules |
| `POST` | `/api/v1/strategy/evaluate-dry-run` | Preview without persistence |
| `GET` | `/api/v1/strategy/setups` | List trade setups |
| `GET` | `/api/v1/strategy/setups/{id}` | Single setup + bias + evaluations |
| `GET` | `/api/v1/strategy/bias` | Recent market biases |
| `GET` | `/api/v1/strategy/rules` | Strategy rule definitions |
| `GET` | `/api/v1/strategy/statistics` | Setup distribution by status/direction/grade |

---

## 7. Limitations

1. **No execution** — setups are advisory only
2. **Single-timeframe** — no HTF/LTF alignment (future)
3. **No risk calculation** — stop reference is a price level, not a risk amount
4. **Target derivation** uses current FVG/liquidity data — not dynamic
5. **No setup evolution** — once generated, setups don't update with new bars
6. **No cross-instrument setups** — each instrument/timeframe is independent
