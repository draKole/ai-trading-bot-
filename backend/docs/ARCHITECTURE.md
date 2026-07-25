# Drake AI Trading — Architecture

## System Overview

Drake AI Trading is a modular algorithmic trading platform with 24 engine services organized in a pipeline architecture. Each phase builds on prior phases — no duplicate logic, single sources of truth, deterministic execution.

## Engine Pipeline

### Core Analysis (Phases 1-4)
| Engine | Purpose |
|--------|---------|
| Market Data | OHLCV intake, bar aggregation |
| Market Structure | Swing points, market structure breaks, trend classification |
| Liquidity | Liquidity level detection, sweeps, liquidity voids |
| FVG | Fair Value Gap identification and lifecycle tracking |
| Order Blocks | Order block detection, mitigation, lifecycle |
| SMT | Smart Money Technique divergence detection |
| Confluence | Multi-factor signal confluence scoring |
| Strategy | Market bias, trade setup generation |
| Risk | Per-trade risk assessment, rule evaluation |
| Position Sizing | Position size recommendation |
| Trade Management | Managed trade lifecycle, trade events |

### Simulation & Testing (Phase 5)
| Engine | Purpose |
|--------|---------|
| Replay | Bar-by-bar historical replay with no-lookahead enforcement |
| Backtesting | Strategy evaluation against historical data |
| Analytics | Performance metrics: Sharpe, Sortino, Calmar, drawdowns, rolling returns |

### Trading Execution (Phase 6)
| Engine | Purpose |
|--------|---------|
| Paper Trading | Simulated execution with slippage, commission, multi-account |
| Live Trading | Broker integration via abstract BrokerAdapter, safety controls |
| Broker | Tradovate adapter (extensible to other brokers) |

### Operations (Phase 7)
| Engine | Purpose |
|--------|---------|
| Monitoring | Health checks, alerts, audit logging, performance metrics |
| Infrastructure | Docker, docker-compose, deployment API |
| Security | Authentication, authorization, secrets, encryption |

### Portfolio & Strategy (Phase 8)
| Engine | Purpose |
|--------|---------|
| Portfolio | Multi-account coordination, capital allocation, portfolio risk |
| Optimization | Grid/random search, walk-forward, Monte Carlo, strategy comparison |
| Scanner | Multi-symbol/timeframe scanning, opportunity scoring, watchlists |

### Command Center (Phase 9)
| Engine | Purpose |
|--------|---------|
| Dashboard | Read-only aggregation of all subsystems: widgets, timeline, snapshots |

## Design Principles

1. **Engine/Service/Model/API pattern**: Every phase follows `services/{name}/engine.py` (pure logic), `services/{name}/service.py` (persistence), `models/{name}.py` (ORM), `api/{name}.py` (FastAPI router).
2. **Deterministic**: Same inputs always produce same outputs. Explicit seeds, no randomness without seed.
3. **No future data**: Historical simulations enforce strict temporal ordering.
4. **Single source of truth**: Risk Engine owns per-trade risk. BrokerAdapter owns execution. Market Data owns price data. No engine duplicates another's logic.
5. **DateTime**: Always `datetime.now(datetime.UTC)`. Never `utcnow()`.
6. **Tests**: Every engine is fully tested. 723 tests total, 0 failures, full regression green on every commit.

## Database

22 Alembic migrations (001-023), 88+ tables across all modules. SQLAlchemy 2.0 async with asyncpg. Shared Base, central session management.

## API

Single FastAPI application with 30+ routers registered under a unified `api_router`. Health check at `/health`, version at `/infrastructure/version`.

## Deployment

Docker multi-stage build (builder + production), docker-compose with 4 services (api, postgres, redis, workers). Non-root `drake` user, health checks on all services.
