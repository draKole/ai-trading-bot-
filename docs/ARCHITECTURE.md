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
| Market Data | 1 | Interface defined |
| Market Structure | 2 | Interface defined |
| Liquidity Engine | 2 | Interface defined |
| FVG Engine | 2 | Interface defined |
| Order Block Engine | 2 | Interface defined |
| SMT Engine | 2 | Interface defined |
| Session Engine | 2 | Interface defined |
| Bias Engine | 2 | Interface defined |
| Strategy Engine | 3 | Interface defined |
| Confluence Scorer | 3 | Interface defined |
| Risk Engine | 5 | Interface defined |
| Position Sizing | 5 | Interface defined |
| Broker Adapter | 7 | Interface defined |
| Order Manager | 7 | Interface defined |
| Backtesting | 4 | Interface defined |
| Paper Trading | 5 | Interface defined |
| Trade Journal | 5 | Interface defined |
| Analytics | 6 | Interface defined |
| Dashboard | 6 | Interface defined |
| AI Analysis | 6+ | Interface defined |

## Technology Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic
- **Database:** PostgreSQL 16 + TimescaleDB (hypertables for OHLCV)
- **Cache:** Redis (kill switch, pub/sub, session state)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS
- **Data:** Polars (primary), Pandas (fallback), yfinance (initial provider)
- **Charts:** TradingView Lightweight Charts

## Key Design Decisions

1. **Risk engine has veto power** — independent from signal generation
2. **Broker-agnostic** — abstract adapter interface
3. **PAPER by default** — LIVE gated by `LIVE_ALLOWED=false`
4. **All signals journaled** — including rejected ones, with reasons
5. **Bar-close confirmation** — no mid-bar execution (eliminates look-ahead bias)
