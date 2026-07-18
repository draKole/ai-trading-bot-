# Database Schema

## Technology
PostgreSQL 16 + TimescaleDB extension for time-series optimization.

## Major Tables (planned)

| Table | Purpose | Hypertable? | Status |
|-------|---------|-------------|--------|
| instruments | Futures contract specs | No | ✅ Phase 1A |
| bars | OHLCV bars (all timeframes) | **Yes** | ✅ Phase 1A |
| market_structure_events | Swings, BOS, CHoCH, MSS | No | ✅ Phase 1B |
| liquidity_levels | Active liquidity levels + config | No | ✅ Phase 2A |
| liquidity_events | Sweeps, breaks, rejections | No | ✅ Phase 2A |
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
