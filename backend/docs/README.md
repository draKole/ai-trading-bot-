# Drake AI Trading

Algorithmic trading platform with modular engine pipeline architecture.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Run tests
PYTHONDONTWRITEBYTECODE=1 python -m pytest -v

# Start API server
uvicorn app.main:app --reload
```

## Architecture

24 engine services in a pipeline: Market Data → Structure → Liquidity → FVG → Order Blocks → SMT → Confluence → Strategy → Risk → Position Sizing → Trade Management → Replay → Backtesting → Analytics → Paper Trading → Live Trading → Monitoring → Security → Portfolio → Optimization → Scanner → Dashboard.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full details.

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, engine pipeline, design principles |
| [DASHBOARD.md](docs/DASHBOARD.md) | Operator dashboard, widgets, timeline, permission model |
| [PERFORMANCE_ANALYTICS.md](docs/PERFORMANCE_ANALYTICS.md) | Backtesting analytics and metrics |
| [PAPER_TRADING.md](docs/PAPER_TRADING.md) | Paper trading engine documentation |
| [LIVE_BROKER.md](docs/LIVE_BROKER.md) | Broker adapter and live trading |
| [MONITORING.md](docs/MONITORING.md) | Production monitoring and alerts |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker deployment and infrastructure |
| [SECURITY.md](docs/SECURITY.md) | Authentication, authorization, encryption |
| [PORTFOLIO.md](docs/PORTFOLIO.md) | Multi-account portfolio management |
| [OPTIMIZATION.md](docs/OPTIMIZATION.md) | Strategy optimization and walk-forward analysis |
| [SCANNER.md](docs/SCANNER.md) | Multi-market scanner and opportunity ranking |

## Testing

723 tests, 0 failures. Run with:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -v
```

## Database

22 Alembic migrations, 88+ tables. SQLAlchemy 2.0 async with PostgreSQL.

```bash
alembic upgrade head
```

## API

FastAPI on port 8000. Health check at `/health`, API docs at `/docs`.
