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
| Order Manager | 7 | Interface defined |
| Backtesting | 4 | Interface defined |
| Paper Trading | 5 | Interface defined |
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
