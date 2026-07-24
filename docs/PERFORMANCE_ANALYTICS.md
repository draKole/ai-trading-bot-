# Performance Analytics Engine — Deterministic Strategy Analysis

## Overview

The Performance Analytics Engine analyzes completed backtest data from Phase 5B to produce advanced metrics, reports, and strategy comparisons. It never processes historical bars directly — all calculations are pure functions operating on trade data.

## Architecture

```
BacktestRun + BacktestTrade + BacktestMetrics (Phase 5B)
                        ↓
                 AnalyticsController
                        ↓
          ┌─────────────┼─────────────┐
          ↓             ↓             ↓
    Risk Metrics    Return Metrics  Trade Analytics
    (Sharpe/Sortino (CAGR/Monthly)  (Distributions)
     /Calmar)
          ↓             ↓             ↓
          └─────────────┼─────────────┘
                        ↓
                 generate_report()
                        ↓
          ┌─────────────┼─────────────┐
          ↓             ↓             ↓
    Executive      Risk        Performance
    Summary       Summary       Summary
                        ↓
                  Chart Datasets
```

---

## 1. Risk-Adjusted Returns

| Metric | Formula | Description |
|--------|---------|-------------|
| **Sharpe Ratio** | (mean excess return / σ) × √252 | Risk-adjusted return using total volatility. Annualized. |
| **Sortino Ratio** | (mean return − target) / σ_downside × √252 | Only penalizes downside volatility. |
| **Calmar Ratio** | CAGR / \|max drawdown %\| | Return per unit of worst-case risk. |

All ratios return 0.0 for insufficient data (fewer than 2 returns, zero variance/deviation).

---

## 2. Drawdown Analytics

| Metric | Description |
|--------|-------------|
| **Average Drawdown** | Mean of all non-zero drawdowns |
| **Max DD Duration** | Longest consecutive trades in drawdown |
| **Recovery Time** | Trades from max drawdown to recovery |
| **Recovery Factor** | Net profit / max drawdown |
| **Ulcer Index** | √(mean of squared drawdown percentages) |

---

## 3. Return Analytics

| Metric | Description |
|--------|-------------|
| **CAGR** | Compound annual growth rate from equity curve |
| **Monthly Returns** | P&L bucketed by year-month |
| **Best/Worst Month** | Highest/lowest monthly return |
| **Avg Monthly Return** | Mean across all months |

---

## 4. Trade Analytics

| Metric | Description |
|--------|-------------|
| **Avg/Median Hold Time** | Trade duration statistics |
| **Avg Winning/Losing Hold Time** | Duration by outcome |
| **Avg Time Between Trades** | Gap between exit and next entry |
| **P&L Distribution** | 10-bucket histogram of trade P&Ls |
| **R-Multiple Distribution** | 10-bucket histogram of R-multiples |
| **Win/Loss Histogram** | Counts by outcome |
| **Consecutive Distribution** | Frequency of streak lengths |

---

## 5. Rolling Analytics

Sliding window (default 10 trades) over trade sequence:

| Metric | Description |
|--------|-------------|
| **Rolling Equity** | Balance after each trade |
| **Rolling Drawdown** | Drawdown % after each trade |
| **Rolling Win Rate** | Win rate over last N trades |
| **Rolling Expectancy** | Expectancy over last N trades |

---

## 6. Reports

`generate_report()` produces a complete JSON-serializable report:

| Section | Contents |
|---------|----------|
| **Executive Summary** | Key metrics at a glance |
| **Risk Summary** | Sharpe, Sortino, Calmar, drawdown stats |
| **Performance Summary** | CAGR, monthly returns, best/worst |
| **Trade Statistics** | Durations, distributions, histograms |
| **Drawdown Analysis** | Detailed drawdown metrics |
| **Monthly Performance** | Month-by-month breakdown |
| **Charts** | Datasets for equity curve, drawdown, monthly returns, trade dist, rolling stats |

---

## 7. Strategy Comparison

`compare_strategies()` accepts multiple run results and produces:

- Per-run metrics table
- Best/worst run identification
- Aggregate statistics (avg net profit, avg win rate, etc.)

---

## 8. Database Schema

### `analytics_reports` — 6 columns
id, run_id (FK→backtest_runs), report_type, metrics_json, charts_json, summary_json, created_at.

Index: run_id.

### `strategy_comparisons` — 4 columns
id, run_ids (JSON array), comparison_json, created_at.

---

## 9. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/analytics/generate` | Generate + persist report |
| `POST` | `/api/v1/analytics/compare` | Compare multiple runs |
| `GET` | `/api/v1/analytics/reports` | List reports |
| `GET` | `/api/v1/analytics/reports/{id}` | Full report |
| `GET` | `/api/v1/analytics/reports/{id}/summary` | Executive summary only |
| `GET` | `/api/v1/analytics/reports/{id}/charts` | Chart datasets only |
| `GET` | `/api/v1/analytics/statistics` | Global stats |

---

## 10. Limitations

1. No actual chart rendering — provides JSON datasets only.
2. Single-run focus — cross-run comparisons are basic.
3. No statistical significance tests (t-test, Monte Carlo).
4. Risk-free rate is fixed at 2% annual.
5. Monthly bucketing uses trade entry timestamps only.
