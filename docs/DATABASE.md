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
| fair_value_gaps | FVGs with lifecycle tracking | No | ✅ Phase 2B |
| fvg_lifecycle_events | State transition log | No | ✅ Phase 2B |
| order_blocks | BOS/CHoCH-triggered OBs | No | ✅ Phase 2C |
| ob_lifecycle_events | State transition log | No | ✅ Phase 2C |
| smt_events | SMT divergence detections | No | ✅ Phase 2D |
| smt_pair_configs | Instrument pair configs | No | ✅ Phase 2D |
| confluence_snapshots | Unified market state | No | ✅ Phase 3A |
| confluence_rule_results | Rule evaluation results | No | ✅ Phase 3A |
| confluence_rules | Rule definitions | No | ✅ Phase 3A |
| market_biases | Directional bias | No | ✅ Phase 3B |
| trade_setups | Advisory trade setups | No | ✅ Phase 3B |
| strategy_rules | Strategy rule definitions | No | ✅ Phase 3B |
| strategy_evaluations | Rule evaluation results | No | ✅ Phase 3B |
| risk_reports | Risk evaluation reports | No | ✅ Phase 4A |
| risk_rules | Risk rule definitions | No | ✅ Phase 4A |
| risk_evaluations | Individual risk checks | No | ✅ Phase 4A |
| position_recommendations | Position size recs | No | ✅ Phase 4B |
| position_sizing_rules | Sizing rule definitions | No | ✅ Phase 4B |
| position_sizing_evaluations | Constraint check results | No | ✅ Phase 4B |
| risk_events | Kill switch activations, etc. | No |
| backtest_runs | Backtest configuration + results | No |
| backtest_trades | Individual backtest trades | No |
| paper_runs | Paper trading sessions | No |
| audit_logs | All system actions | No |
| strategies | Strategy versions + config | No |
| risk_profiles | Risk parameter sets | No |
| users | Authentication | No |

TimescaleDB hypertables are used for append-heavy time-series tables (bars, account_snapshots).
