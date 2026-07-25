# Strategy Optimization & Walk-Forward Analysis

## Overview

Optimizes trading strategy parameters using grid search, random search, walk-forward validation, Monte Carlo simulation, and strategy comparison. Coordinates existing engines — never duplicates Replay/Backtesting/Analytics logic.

---

## 1. Optimization Methods

### Grid Search
Exhaustive evaluation of all parameter combinations from defined ranges and steps. Supports 10,000+ combinations.

### Random Search
Random sampling from parameter ranges with configurable seed for reproducibility. Different seeds produce different samples — same seed always produces identical results.

### Walk-Forward
Rolling in-sample optimization + out-of-sample validation windows. Configurable window sizes.

### Monte Carlo
Trade sequence randomization to estimate equity distribution, drawdown risk, and risk-of-ruin. Configurable iterations (100-10,000).

---

## 2. Parameter Management

`ParamRange(name, min_val, max_val, step)`:

```python
ParamRange("min_rr", 2.0, 4.0, 0.5)  # → 2.0, 2.5, 3.0, 3.5, 4.0
```

---

## 3. Strategy Comparison

`compare_strategies(results)` ranks by net profit (extensible to any metric). Returns top 10 ranked with all metrics.

---

## 4. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/optimization/runs` | List runs |
| `GET` | `/optimization/runs/{id}` | Get run |
| `POST` | `/optimization/grid-search` | Run grid search |
| `POST` | `/optimization/monte-carlo` | Run Monte Carlo |
| `POST` | `/optimization/compare` | Compare strategies |
| `GET` | `/optimization/statistics` | Stats |

## 5. Database

5 tables: optimization_runs, parameter_sets, optimization_results, walk_forward_runs, monte_carlo_runs.
