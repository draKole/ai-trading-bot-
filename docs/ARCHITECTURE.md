# Architecture

Drake AI Trading follows a modular, pipeline-oriented architecture. The core principle: **every module has a single responsibility and communicates through well-defined data objects.**

## System Overview

```
Market Data → Normalization → Feature Engines → Confluence Scorer → Setup Engine
    → Signal Generator → Risk Engine (VETO) → Position Sizing → Order Manager
    → Broker Adapter → Execution → Trade Journal → Analytics
```

## Module Map

| Module | Phase | Status |
|--------|-------|--------|
| Market Data | 1A | ✅ Complete |
| Market Structure | 1B | ✅ Complete |
| Liquidity Engine | 2A | ✅ Complete |
| FVG Engine | 2B | ✅ Complete |
| Order Block Engine | 2C | ✅ Complete |
| SMT Engine | 2D | ✅ Complete |
| Confluence Engine | 3A | ✅ Complete |
| Strategy Engine | 3B | ✅ Complete |
| Risk Engine | 4A | ✅ Complete |
| Position Sizing | 4B | ✅ Complete |
| Trade Management | 4C | ✅ Complete |
| Historical Replay | 5A | ✅ Complete |
| Backtesting | 5B | ✅ Complete |
| Performance Analytics | 5C | ✅ Complete |
| Paper Trading | 6A | ✅ Complete |
| Live Broker Integration | 6B | ✅ Complete |
| Production Monitoring | 7A | ✅ Complete |
| Deployment & Infrastructure | 7B | ✅ Complete |
| Order Manager | 7 | Interface defined |
| Trade Journal | 5 | Interface defined |
| Analytics | 6 | Interface defined |
| Dashboard | 6 | Interface defined |
| AI Analysis | 6+ | Interface defined |

## Technology Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic
- **Database:** PostgreSQL 16 + TimescaleDB (hypertables for OHLCV, regular tables for structure events)
- **Cache:** Redis (kill switch, pub/sub, session state)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS
- **Data:** Polars (primary), Pandas (fallback), yfinance (initial provider)
- **Charts:** TradingView Lightweight Charts

## Recent Phases

### Phase 7B — Deployment & Infrastructure
- Multi-stage Dockerfile (builder + production, non-root user, health check)
- Docker Compose: API + PostgreSQL + Redis + workers with health checks
- Infrastructure API: deployment status, version, readiness, liveness, config validation, diagnostics
- Environment-driven configuration with secrets protection
- Alembic 018 placeholder migration
- 20 tests: config, secrets, startup, API endpoints, Docker/Compose file existence
- Full documentation in `docs/DEPLOYMENT.md`

### Phase 7A — Production Monitoring
- Read-only observability: health checks, metrics, alerts, audit logging
- 7 health endpoints: system, database, broker, market-data, live/paper trading, workers
- Alert lifecycle: create → acknowledge → resolve with severity levels
- Immutable audit logs: signals, risk, sizing, management, broker, manual actions
- Time-series metrics with aggregation and tags
- Dashboard API combining health + metrics + alerts
- 20 API endpoints total
- 29 tests (all pass, no DB dependencies)
- Full documentation in `docs/MONITORING.md`

### Phase 6B — Live Broker Integration
- Abstract BrokerAdapter interface — connect, place/modify/cancel orders, positions, account
- TradovateAdapter: simulated implementation with fill, cancel, position tracking
- LiveTradingController: session management, order routing, sync
- SafetyController: kill switch, max positions, duplicate prevention, daily loss limit
- 14 API endpoints for connect, orders, positions, executions, emergency stop
- 32 tests (1 DB-dependent skipped)
- Full documentation in `docs/LIVE_BROKER.md`

### Phase 6A — Paper Trading Engine
- Simulated execution with the full strategy pipeline
- Multiple concurrent accounts, market/limit/stop orders
- Realistic fills: slippage, commission, partial fills
- Position tracking: long/short, open/closed, P&L mark-to-market
- Session state export/import for recovery
- 11 API endpoints for session/order/position/execution management
- 42 tests (1 DB-dependent skipped)
- Full documentation in `docs/PAPER_TRADING.md`

### Phase 5C — Performance Analytics
- Pure-function analytics consuming Phase 5B data — never touches bars
- Risk-adjusted: Sharpe, Sortino, Calmar ratios
- Advanced drawdown: ulcer index, recovery factor, duration
- CAGR, monthly returns, best/worst month
- Trade distributions, histograms, rolling analytics
- Strategy comparison, full report generation, chart datasets
- 7 API endpoints
- 37 tests (2 DB-dependent skipped)
- Full documentation in `docs/PERFORMANCE_ANALYTICS.md`

### Phase 5B — Backtesting Engine
- Wraps Phase 5A ReplayController for deterministic strategy evaluation
- All 27 performance metrics: P&L, win rate, profit factor, expectancy, drawdown, streaks, directional
- Equity curve generation after every closed trade
- Parameter sweeps: grid search across config combinations
- 8 API endpoints: run, dry-run, batch, sweeps, trades, metrics, statistics
- 40 tests — deterministic output verified
- Full documentation in `docs/BACKTESTING.md`

### Phase 5A — Historical Replay Engine
- Deterministic bar-by-bar replay through complete engine pipeline
- State machine: IDLE → RUNNING → PAUSED → STOPPED
- Strict no-lookahead: bar N can only see bars [0..N]
- Six replay modes: candle_by_candle, continuous, until_timestamp, until_event, by_session, by_trading_day
- Per-bar ReplaySnapshot captures full pipeline state
- ReplayEvent records every engine event with source attribution
- 11 API endpoints — start, pause, resume, step, jump_to, dry-run
- 53 tests — deterministic output verified
- Full documentation in `docs/HISTORICAL_REPLAY.md`

### Phase 1A — Market Data Foundation
- Multi-provider data ingestion (CSV, yfinance)
- Polars-based bar aggregation across 7 timeframes (1m→3m→5m→15m→1h→4h→1d)
- Validation engine (duplicates, gaps, overlap detection)
- TimescaleDB hypertable for OHLCV storage
- 38 tests, 1 DB-dependent skip

### Phase 2A — Liquidity Engine (Current)
- Session engine with timezone-aware session detection (Asia/London/NY AM/NY PM)
- 18 liquidity level types: PDH/PDL, PWH/PWL, PMH/PML, session highs/lows, equal highs/lows, swing liquidity, internal liquidity
- 6 event types: approached, touched, swept, rejected, broken, invalidated
- All definitions mathematical and deterministic
- Config snapshot serialized with every level/event for auditability
- 22 tests with handcrafted OHLCV sequences
- Full documentation in `docs/LIQUIDITY_ENGINE.md`

### Phase 1B — Market Structure Engine
- Swing point detection with configurable lookback/confirmation/distance
- HH/HL/LH/LL classification
- BOS (Break of Structure), CHoCH (Change of Character), MSS (Market Structure Shift)
- All definitions are mathematical and deterministic
- Config snapshot serialized with every event for auditability
- 20 tests with handcrafted OHLCV sequences
- Full documentation in `docs/MARKET_STRUCTURE.md`

## Key Design Decisions

1. **Risk engine has veto power** — independent from signal generation
2. **Broker-agnostic** — abstract adapter interface
3. **PAPER by default** — LIVE gated by `LIVE_ALLOWED=false`
4. **All signals journaled** — including rejected ones, with reasons
5. **Bar-close confirmation** — no mid-bar execution (eliminates look-ahead bias)
