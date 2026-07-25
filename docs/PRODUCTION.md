# Production Architecture — Drake AI Trading v1.0

## System Architecture

Drake AI Trading is a modular algorithmic trading platform with 25 engine services in a pipeline architecture. The platform runs as a single FastAPI application with PostgreSQL backend, Redis caching, and Docker deployment.

## Production Topology

```
                    ┌─────────────┐
                    │  Nginx/ALB  │  (HTTPS termination, rate limiting)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   API Pod   │  FastAPI + Uvicorn (4 workers)
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──┐  ┌──────▼──┐  ┌──────▼──┐
       │PostgreSQL│  │  Redis  │  │ Workers │  (background jobs)
       └──────────┘  └─────────┘  └─────────┘
```

## Engine Pipeline

### Core Analysis (7 engines)
Market Data → Market Structure → Liquidity → FVG → Order Blocks → SMT → Confluence

### Strategy & Risk (4 engines)
Strategy → Risk → Position Sizing → Trade Management

### Simulation & Testing (3 engines)
Replay → Backtesting → Analytics

### Trading Execution (3 engines)
Paper Trading → Live Trading → Broker Adapter (Tradovate)

### Operations (3 engines)
Monitoring → Security → Infrastructure

### Portfolio & Strategy (3 engines)
Portfolio → Optimization → Scanner

### Command Center (2 engines)
Dashboard → Copilot

## Performance Characteristics

| Component | Baseline | Scale Target |
|-----------|----------|-------------|
| API throughput | 500 req/s | 2000 req/s |
| Dashboard snapshot | <100ms | <200ms |
| Scanner (500 symbols) | <2s | <5s |
| Backtest (1yr daily) | <30s | <60s |
| DB connection pool | 10-30 | 50 |
| Concurrent sessions | 100 | 500 |

## Disaster Recovery

1. **Database**: PostgreSQL streaming replication with 15-minute RPO. Point-in-time recovery via WAL archiving.
2. **State**: All engine state is in the database. No in-memory state that can't be rebuilt.
3. **Backup**: Daily pg_dump + continuous WAL shipping to S3.
4. **Recovery time**: <30 minutes for full restore from backup.

## Capacity Planning

| Resource | Minimum | Recommended | Notes |
|----------|---------|-------------|-------|
| CPU | 2 cores | 4+ cores | API workers scale with CPU |
| Memory | 4 GB | 8+ GB | Scanner/backtesting are memory-intensive |
| Disk | 20 GB | 100+ GB | Market data grows ~1GB/month/symbol |
| PostgreSQL | 2 vCPU, 4 GB | 4 vCPU, 16 GB | Index-heavy workload |

## Maintenance Procedures

### Daily
- Health check verification (`/health`)
- Alert review
- Broker connectivity check

### Weekly
- Log rotation
- DB vacuum analyze
- Performance metric review

### Monthly
- Dependency updates review
- Backup restore test
- Capacity review

### Quarterly
- Full DR drill
- Security audit
- Performance benchmark rerun

## Monitoring & Alerting

**Critical alerts (immediate response):**
- Broker disconnect
- API health check failure
- Database connection loss
- Any security event (unauthorized access attempt)

**Warning alerts (review within 1 hour):**
- High API latency (>500ms p95)
- Elevated error rate (>1%)
- High memory usage (>80%)
- Risk limit breaches

## Support Model

| Tier | Owner | Response |
|------|-------|----------|
| Tier 1 | DevOps | Initial triage, restart services |
| Tier 2 | Platform Engineering | Code-level debugging, hotfixes |
| Tier 3 | Engine specialists | Per-engine deep debugging |
| Escalation | Lead Architect | Architecture-level issues |

## Upgrade Procedure

1. Run pre-upgrade health check
2. Take database snapshot
3. Apply migrations: `alembic upgrade head`
4. Deploy new API containers (blue/green)
5. Verify health endpoints
6. Run smoke tests
7. Switch traffic to new containers
8. Monitor for 15 minutes before declaring complete

## Rollback Procedure

1. Switch traffic back to previous containers
2. Run rollback migration: `alembic downgrade -1`
3. Verify health
4. Investigate failure, prepare hotfix

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection | Yes |
| `REDIS_URL` | Redis connection | Yes |
| `BROKER_API_KEY` | Tradovate API key | Yes |
| `SECRET_KEY` | JWT signing key | Yes |
| `ENCRYPTION_KEY` | Data encryption key | Yes |
| `LOG_LEVEL` | Logging verbosity | No (default: INFO) |
| `ENVIRONMENT` | production/staging | No (default: production) |
