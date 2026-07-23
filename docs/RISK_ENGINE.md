# Risk Engine — Setup Evaluation & Validation

## Overview

The Risk Engine evaluates Trade Setups from the Strategy Engine against configurable risk criteria. It produces Risk Reports with validation results, classification, and numerical scoring — without executing, sizing, or managing any trades.

## Architecture

```
TradeSetup + MarketBias → RiskEngine → RiskAssessment
                                            ↓
                                      ValidationSummary (PASS/FAIL/WARN per rule)
                                            ↓
                                      RiskScore + RiskClassification
                                            ↓
                                          RiskReport
```

| Component | File | Purpose |
|-----------|------|---------|
| `compute_assessment()` | `engine.py` | Numerical risk metrics (R:R, stop %, EV) |
| `validate_setup()` | `engine.py` | Configurable rule-based validation |
| `compute_risk_score()` | `engine.py` | Weighted composite risk score (0-100) |
| `classify_risk()` | `engine.py` | 5-tier classification |
| `evaluate_risk()` | `engine.py` | Full pipeline → RiskReport |
| `RiskService` | `service.py` | DB persistence and queries |

---

## 1. Risk Assessment

| Metric | Formula | Description |
|--------|---------|-------------|
| `stop_distance_points` | \|entry - stop\| | Absolute price distance |
| `stop_distance_pct` | (stop_dist / entry) × 100 | Stop as % of price |
| `reward_risk_ratio` | target_1_pct / stop_pct | R:R using nearest target |
| `best_reward_risk` | max_target_pct / stop_pct | R:R using furthest target |
| `mfe_estimate` | best_target_pct | Maximum Favorable Excursion estimate |
| `mae_estimate` | stop_distance_pct | Maximum Adverse Excursion estimate |
| `expected_value` | 0.5 × avg_win − 0.5 × avg_loss | Simplified EV (50% win rate) |
| `volatility_pct` | (ATR / price) × 100 | External input |
| `setup_stability_score` | 0-100 | Composite: entry + stop + targets + R:R + setup score |

### Entry Price Fallback
1. `preferred_entry` if non-null and >0
2. Midpoint of `entry_zone_low` / `entry_zone_high`
3. `entry_zone_low` as last resort

---

## 2. Validation Rules

| Rule | Operator | Default | Description |
|------|----------|---------|-------------|
| `min_reward_risk` | ≥ | 2.0 | Minimum R:R ratio |
| `max_stop_distance` | ≤ | 1.0% | Maximum stop as % of price |
| `min_confidence` | ≥ | Medium | Minimum Market Bias confidence |
| `min_strategy_grade` | ≥ | C+ | Minimum bias grade |
| `session_allowed` | in | London, NY AM, NY PM | Allowed sessions |
| `regime_allowed` | in | trending, breakout | Allowed market regimes |
| `volatility` | ≤ | 3.0% | Maximum ATR as % of price |

### Result Types
- **PASS**: Within threshold
- **WARN**: Between warn and fail thresholds
- **FAIL**: Outside threshold

Each check returns detail with expected vs actual values.

---

## 3. Risk Scoring (0-100)

| Component | Weight | Max | Formula |
|-----------|--------|-----|---------|
| Reward/Risk | 30 | 30 | min(RR / min_rr, 2.0) × 15 |
| Stop distance | 20 | 20 | min(max_pct / actual_pct, 1.5) × 13.3 |
| Confidence | 15 | 15 | (numeric_conf / 5) × 15 |
| Grade | 10 | 10 | (numeric_grade / 10) × 10 |
| Volatility | 10 | 10 | min(max_vol / actual_vol, 1.5) × 6.7 |
| Regime | 10 | 10 | 10 if allowed, 0 otherwise |
| Session | 5 | 5 | 5 if allowed, 0 otherwise |

Score capped at 100.

---

## 4. Risk Classification

| Score | Classification |
|-------|---------------|
| ≥ 90 | Very Low |
| ≥ 75 | Low |
| ≥ 60 | Medium |
| ≥ 40 | High |
| < 40 | Extreme |

All thresholds configurable.

---

## 5. Risk Report

| Field | Description |
|-------|-------------|
| `setup_id` | References Trade Setup |
| `overall_risk_score` | 0-100 composite |
| `risk_classification` | Very Low → Extreme |
| `assessment` | All numerical metrics |
| `validation` | PASS/FAIL/WARN per rule |
| `supporting_evidence` | Passed rules with details |
| `contradicting_evidence` | Failed rules with details |
| `failure_reasons` | Only FAIL items |

---

## 6. Database Schema

### `risk_reports`
19 columns: setup_id, instrument, timeframe, direction, overall_risk_score, risk_classification, key metrics (R:R, stop %, EV, stability, volatility), validation/evidence JSON, config snapshot.

Indexes: setup_id, instrument, timeframe, risk_classification.

### `risk_rules`
11 columns: name (unique), description, rule_type, threshold, warn_threshold, operator, field, group, priority, enabled.

### `risk_evaluations`
6 columns: report_id, setup_id, rule_name, result (PASS/FAIL/WARN), detail.

Indexes: report_id, setup_id, rule_name.

---

## 7. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/risk/evaluate` | Evaluate latest setup + store |
| `POST` | `/api/v1/risk/evaluate-dry-run` | Preview without persistence |
| `GET` | `/api/v1/risk/reports` | List risk reports |
| `GET` | `/api/v1/risk/reports/{id}` | Single report + evaluations |
| `GET` | `/api/v1/risk/rules` | Risk rule definitions |
| `GET` | `/api/v1/risk/statistics` | Distribution by classification |

---

## 8. Limitations

1. **No position sizing** — evaluates risk quality, not quantity
2. **Simplified EV** — assumes fixed 50% win rate for scoring
3. **Volatility is external** — must be provided, not computed
4. **Single-timeframe** — no multi-TF risk assessment
5. **No correlation risk** — each setup evaluated independently
6. **No dynamic thresholds** — thresholds don't adapt to market conditions
