# Deployment & Infrastructure

## Overview

Production-grade deployment with Docker multi-stage builds, environment-driven configuration, secrets management, health checks, and CI/CD pipeline. Never modifies trading logic.

## Architecture

```
Docker Compose
├── api (FastAPI + Uvicorn, port 8000)
├── postgres (PostgreSQL 16, port 5432)
├── redis (Redis 7, port 6379)
└── workers (background monitoring/metrics)
```

---

## 1. Docker

### Multi-stage Build
- **Stage 1 (builder):** Install Python dependencies from requirements.txt
- **Stage 2 (production):** Copy app code, run as non-root `drake` user
- Health check: HTTP GET to `/health` every 30s

### docker-compose.yml
- 4 services: api, postgres, redis, workers
- Health checks on postgres (`pg_isready`) and redis (`redis-cli ping`)
- Volume for PostgreSQL data persistence
- Environment-driven config via env vars

### .dockerignore
Excludes: pycache, .env, logs, .git, venv, builds, secrets

---

## 2. Configuration

Environment-driven via `app/core/config.py`:

| Environment | Description |
|-------------|-------------|
| `TRADING_MODE` | BACKTEST / PAPER / LIVE |
| `LIVE_ALLOWED` | Must be explicitly `true` for LIVE |
| `POSTGRES_*` | DB connection params |
| `REDIS_*` | Redis connection params |
| `SECRET_KEY` | JWT signing key |
| `LOG_LEVEL` | DEBUG / INFO / WARNING / ERROR |

Env vars override defaults. Secrets never in source control.

---

## 3. Infrastructure API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/infrastructure/deployment/status` | Version + status |
| `GET` | `/infrastructure/deployment/version` | Build info |
| `GET` | `/infrastructure/deployment/readiness` | Readiness probe |
| `GET` | `/infrastructure/deployment/liveness` | Liveness probe |
| `GET` | `/infrastructure/deployment/config` | Config validation |
| `GET` | `/infrastructure/deployment/diagnostics` | Full diagnostics |

---

## 4. Alembic Migration

Version 018_infrastructure — placeholder (no schema changes). Depends on 017_monitoring.

---

## 5. CI/CD Pipeline (Definition)

1. Dependency install
2. Static analysis (ruff)
3. Type checking (mypy)
4. Unit tests (pytest)
5. Migration check (alembic)
6. Docker build

---

## 6. Limitations

1. No Kubernetes/Helm — Docker Compose only
2. No automatic deployment
3. Background workers are stubs
4. No log aggregation (file-based only)
5. No SSL/TLS termination
