# Position Sizing Engine — Contract Quantity Determination

## Overview

The Position Sizing Engine determines appropriate contract quantities from approved Trade Setups, Risk Reports, and Account Configuration. It produces Position Recommendations with constraint validation — advisory only, no execution.

## Architecture

```
TradeSetup + RiskReport + AccountConfig → PositionSizingEngine
                                              ↓
                                         RiskModel (selectable)
                                              ↓
                                         Contract Calculation
                                              ↓
                                         Constraint Validation (6 rules)
                                              ↓
                                         PositionRecommendation
```

---

## 1. Sizing Methods

| Method | Formula | Key Parameter |
|--------|---------|---------------|
| `fixed_dollar` | contracts = fixed_dollar_risk / risk_per_contract | `fixed_dollar_risk` |
| `fixed_percentage` | contracts = (balance × risk_pct) / risk_per_contract | `max_risk_per_trade_pct` |
| `kelly` | f* = (p×b−q)/b, contracts = (balance × kelly_fraction × f*) / risk_per_contract | `kelly_fraction` |
| `fixed_contracts` | contracts = fixed_contract_count | `fixed_contract_count` |
| `volatility_based` | contracts from ATR-adjusted stop distance (placeholder) | `volatility_atr` |

### Dollar Risk Per Contract
```
point_value = tick_value / tick_size  (e.g., $12.50 / 0.25 = $50/pt)
dollar_risk = stop_distance_pts × point_value
```

---

## 2. Constraint Validation — 6 Rules

| Rule | Formula | Type |
|------|---------|------|
| `max_trade_risk` | contracts × risk_per_contract ≤ balance × risk_pct | limit |
| `max_daily_loss` | daily_loss + trade_risk ≤ daily_limit | limit |
| `max_contracts` | contracts ≤ 100 (configurable) | limit |
| `margin` | contracts × margin_per_contract ≤ buying_power | limit |
| `open_positions` | current + 1 ≤ max_open_positions | limit |
| `exposure` | contracts × entry × multiplier ≤ balance × exposure_pct | limit |

---

## 3. Position Recommendation

| Field | Description |
|-------|-------------|
| `recommended_contracts` | Primary recommendation |
| `conservative_contracts` | floor(recommended × 0.5) |
| `max_allowable_contracts` | Capped by risk and margin |
| `dollar_risk_per_contract` | $ at risk per contract |
| `total_dollar_risk` | Total $ at risk |
| `margin_required` | Contracts × margin per contract |
| `capital_utilization_pct` | Margin / balance × 100 |
| `effective_leverage` | Notional / balance |
| `risk_pct_of_account` | Dollar risk / balance × 100 |
| `all_constraints_pass` | All 6 rules PASS |

---

## 4. Account Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `account_balance` | $100,000 | Base capital |
| `buying_power` | 2× balance | Margin buying power |
| `max_risk_per_trade_pct` | 1.0% | Per-trade risk budget |
| `max_daily_loss_pct` | 3.0% | Daily loss limit |
| `max_open_positions` | 5 | Concurrency limit |
| `max_exposure_pct` | 500% | Notional exposure cap |
| `tick_value` | $12.50 | ES-like |
| `tick_size` | 0.25 | ES-like |
| `contract_multiplier` | 50.0 | ES-like |
| `margin_per_contract` | $12,000 | Initial margin |
| `sizing_method` | fixed_percentage | Selectable |
| `kelly_fraction` | 0.25 | Conservative Kelly |

---

## 5. Database Schema

### `position_recommendations` — 21 columns
recommendation_id (unique), setup_id, instrument, direction, sizing_method, all contract quantities, dollar values, constraint results JSON, all_constraints_pass, failure_reasons, config snapshot.

### `position_sizing_rules` — 8 columns
name (unique), description, rule_type, threshold, group, priority, enabled.

### `position_sizing_evaluations` — 6 columns
recommendation_id, setup_id, rule_name, status (PASS/FAIL), detail.

---

## 6. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/position-sizing/calculate` | Calculate + store |
| `POST` | `/api/v1/position-sizing/calculate-dry-run` | Preview |
| `GET` | `/api/v1/position-sizing/recommendations` | List |
| `GET` | `/api/v1/position-sizing/recommendations/{id}` | Detail + evaluations |
| `GET` | `/api/v1/position-sizing/rules` | Rule definitions |
| `GET` | `/api/v1/position-sizing/statistics` | Distribution stats |

---

## 7. Limitations

1. **Advisory only** — no order execution
2. **Simplified Kelly** — assumes fixed win rate and payoff ratio
3. **Volatility-based is a placeholder** — uses ATR as alternate stop distance
4. **No portfolio-level sizing** — each setup sized independently
5. **No dynamic margin** — uses static margin_per_contract
6. **No scaling-in logic** — single entry only
