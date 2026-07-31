#!/bin/bash
# Drake AI Trading — Docker Entrypoint
#
# Responsibilities:
#   1. Wait for PostgreSQL to accept connections
#   2. Run Alembic migrations (idempotent — safe for fresh starts and restarts)
#   3. Start the API server
#
# This script runs as PID 1 inside the container. All environment variables
# are supplied by docker-compose or the deployment environment.

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_USER="${POSTGRES_USER:-drake}"
DB_NAME="${POSTGRES_DB:-drake_trading}"

MAX_RETRIES=30
RETRY_INTERVAL=2

# ── Functions ──────────────────────────────────────────────────

wait_for_postgres() {
    echo "[entrypoint] Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
    local attempt=0
    while [ $attempt -lt $MAX_RETRIES ]; do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q 2>/dev/null; then
            echo "[entrypoint] PostgreSQL is ready."
            return 0
        fi
        attempt=$((attempt + 1))
        echo "[entrypoint] Attempt ${attempt}/${MAX_RETRIES}: PostgreSQL not ready — retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    done
    echo "[entrypoint] ERROR: PostgreSQL did not become ready after ${MAX_RETRIES} attempts."
    return 1
}

run_migrations() {
    echo "[entrypoint] Running Alembic migrations..."
    cd /app/backend
    if alembic upgrade head; then
        echo "[entrypoint] Migrations complete."
    else
        echo "[entrypoint] ERROR: Migration failed."
        return 1
    fi
}

start_api() {
    echo "[entrypoint] Starting API server in ${TRADING_MODE:-PAPER} mode..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
}

# ── Main ───────────────────────────────────────────────────────

echo "[entrypoint] Drake AI Trading v1.0.0 — Startup"
echo "[entrypoint] Trading mode: ${TRADING_MODE:-PAPER}"
echo "[entrypoint] Live allowed: ${LIVE_ALLOWED:-false}"

wait_for_postgres
run_migrations
start_api
