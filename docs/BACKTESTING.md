# Backtesting Engine — Deterministic Strategy Evaluation

## Overview

The Backtesting Engine evaluates trading strategy performance over historical data by orchestrating replay sessions (Phase 5A) and analyzing the resulting trades. It wraps `ReplayController` — no duplicate replay logic.

## Architecture

```
BacktestConfig → BacktestController
                      ↓
               ReplayController (Phase 5A)
                      ↓
               Replay Snapshots + Events
                      ↓
               Trade Extraction
                      ↓
        compute_metrics() → BacktestMetrics
                      ↓
               EquityCurve (per-trade points)
                      ↓
               BacktestResult
```

---

## 1. BacktestController

Wraps `ReplayController` internally. Supports three run modes:

| Method | Description |
|--------|-------------|
| `run(bars)` | Single backtest with simplified simulated mode (for testing) or full replay mode |
| `run_batch(bars, configs)` | Multiple backtests with different configs |
| `run_parameter_sweep(bars, sweep)` | Grid search across parameter combinations |

### BacktestConfig

| Field | Default | Description |
|-------|---------|-------------|
| `instrument` | `""` | Trading instrument |
| `timeframe` | `"5m"` | Bar timeframe |
| `start_time` / `end_time` | None | Time boundaries |
| `replay_mode` | `"candle_by_candle"` | Passed to ReplayController |
| `strategy_params` | `{}` | Strategy-specific parameters |
| `initial_balance` | `$100,000` | Starting account equity |
| `commission_per_contract` | `$2.50` | Per-trade cost |
| `slippage_ticks` | `1` | Slippage in ticks |

---

## 2. Performance Metrics

All 27 metrics are computed deterministically from a list of trades:

| Category | Metrics |
|----------|---------|
| **P&L** | Net Profit, Gross Profit, Gross Loss |
| **Counts** | Total Trades, Winning Trades, Losing Trades, Breakeven Trades |
| **Rates** | Win Rate, Loss Rate |
| **Ratios** | Profit Factor (Gross Profit / \|Gross Loss\|) |
| **Averages** | Average Win, Average Loss, Average R |
| **Expectancy** | Win Rate × Avg Win − Loss Rate × Avg Loss |
| **Drawdown** | Max Drawdown ($), Max Drawdown (%) |
| **Streaks** | Max Consecutive Wins, Max Consecutive Losses |
| **Duration** | Average Trade Duration (seconds) |
| **Directional** | Long Trades/Wins/P&L, Short Trades/Wins/P&L |
| **Extremes** | Largest Winner, Largest Loser |

### Determinism Guarantee

`compute_metrics()` is a pure function: identical trade lists produce identical metrics and equity curves every time. Verified by `test_deterministic_same_bars` and `test_determinism`.

---

## 3. Equity Curve

After every closed trade, an `EquityPoint` is generated:

| Field | Description |
|-------|-------------|
| `trade_index` | 0-based trade number |
| `timestamp` | Exit timestamp |
| `account_balance` | Running balance |
| `equity` | Current equity (= balance in backtest) |
| `drawdown` | Peak-to-current decline ($) |
| `drawdown_pct` | Drawdown as percentage |
| `peak_equity` | Highest equity reached so far |

---

## 4. Trade History

Each completed trade is recorded as a `BacktestTrade`:

| Field | Description |
|-------|-------------|
| `trade_id` | UUID |
| `entry_time` / `exit_time` | Entry and exit timestamps |
| `direction` | `"bullish"` or `"bearish"` |
| `quantity` | Number of contracts |
| `entry_price` / `exit_price` | Price levels |
| `stop_price` | Initial stop |
| `risk` | Risk in price points |
| `r_multiple` | R-multiple of the trade |
| `pnl` | Profit/loss in dollars |
| `duration_seconds` | Trade duration |
| `exit_reason` | `"reversal"`, `"end_of_data"`, etc. |
| `strategy_version` | Version identifier |

---

## 5. Parameter Sweeps

`ParamSweepConfig` generates all combinations from a parameter grid:

```python
sweep = ParamSweepConfig(
    instrument="ES",
    param_grid={
        "min_rr": [2.0, 3.0],
        "confidence_threshold": [60, 70],
    },
)
configs = sweep.generate_configs()  # 4 combinations
```

Each combination produces an independent `BacktestResult` with full metrics.

---

## 6. Database Schema

### `backtest_runs` — 10 columns
id, instrument, timeframe, start_time, end_time, status, total_bars, config_json, metrics_json, equity_curve_json.

Indexes: instrument, status.

### `backtest_trades` — 17 columns
id, run_id (FK→backtest_runs), entry_time, exit_time, direction, quantity, entry_price, exit_price, stop_price, risk, r_multiple, pnl, duration_seconds, exit_reason, strategy_version, created_at.

Index: run_id.

### `backtest_metrics` — 28 columns
id, run_id (FK→backtest_runs, unique), net_profit, gross_profit, gross_loss, total_trades, winning_trades, losing_trades, breakeven_trades, win_rate, loss_rate, profit_factor, average_win, average_loss, average_r, expectancy, max_drawdown, max_drawdown_pct, max_consecutive_wins, max_consecutive_losses, average_trade_duration_seconds, long_trades, long_wins, long_pnl, short_trades, short_wins, short_pnl, largest_winner, largest_loser.

Unique constraint: run_id.

---

## 7. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/backtesting/runs` | List runs |
| `GET` | `/api/v1/backtesting/runs/{id}` | Get run details |
| `POST` | `/api/v1/backtesting/run` | Run backtest + persist |
| `POST` | `/api/v1/backtesting/run-dry` | Run without persistence |
| `GET` | `/api/v1/backtesting/runs/{id}/trades` | Get trades for run |
| `GET` | `/api/v1/backtesting/runs/{id}/metrics` | Get metrics for run |
| `GET` | `/api/v1/backtesting/statistics` | Aggregate stats |
| `POST` | `/api/v1/backtesting/sweep` | Parameter sweep |

---

## 8. Limitations

1. Simplified simulation mode uses trend-following logic — not the full engine pipeline. Full replay integration requires live engine callbacks.
2. Commission and slippage are config-only — not yet applied in simulation.
3. Single-instrument, single-timeframe per run.
4. No walk-forward or in-sample/out-of-sample split.
5. No Sharpe ratio, Sortino ratio, or other risk-adjusted metrics.
