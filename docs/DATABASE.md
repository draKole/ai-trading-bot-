# Database Schema

## Technology
PostgreSQL 16 + TimescaleDB extension for time-series optimization.

## Major Tables (planned)

| Table | Purpose | Hypertable? |
|-------|---------|-------------|
| instruments | Futures contract specs | No |
| bars | OHLCV bars (all timeframes) | **Yes** |
| market_structure_events | Swings, BOS, CHoCH, MSS | No |
| liquidity_levels | Session/PDH/PDL levels | No |
| fvgs | Fair Value Gaps + fill status | No |
| order_blocks | Active/historical OBs | No |
| smt_events | Divergence detections | No |
| signals | Generated trade signals | No |
| risk_decisions | Approval/rejection records | No |
| orders | Broker order tracking | No |
| trades | Complete trade records | No |
| account_snapshots | Periodic equity snapshots | **Yes** |
| risk_events | Kill switch activations, etc. | No |
| backtest_runs | Backtest configuration + results | No |
| backtest_trades | Individual backtest trades | No |
| paper_runs | Paper trading sessions | No |
| audit_logs | All system actions | No |
| strategies | Strategy versions + config | No |
| risk_profiles | Risk parameter sets | No |
| users | Authentication | No |

TimescaleDB hypertables are used for append-heavy time-series tables (bars, account_snapshots).
