"""Drake AI Trading — FastAPI Application Entry Point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import check_db_connection
from app.core.redis import check_redis_connection, close_redis
from app.api.router import api_router
from app.api.market_data import autonomous_sync
from app.core.database import async_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle handler.

    On startup:
        - Verify database connectivity
        - Verify Redis connectivity
        - Log the active trading mode
        - Reject unsafe LIVE mode without explicit confirmation
    On shutdown:
        - Close Redis connection gracefully
    """
    # ── Startup ────────────────────────────────────────────────
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()

    status = []
    status.append(f"database={'ok' if db_ok else 'FAILED'}")
    status.append(f"redis={'ok' if redis_ok else 'FAILED'}")
    print(f"Drake AI Trading started in {settings.TRADING_MODE} mode ({', '.join(status)})")

    if settings.TRADING_MODE == "LIVE" and not settings.LIVE_ALLOWED:
        raise RuntimeError(
            "LIVE mode is not allowed — set LIVE_ALLOWED=true in the environment"
        )

    yield

    # ── Shutdown ───────────────────────────────────────────────
    await close_redis()


app = FastAPI(
    title="Drake AI Trading",
    description="Professional automated futures trading platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.TRADING_MODE != "LIVE" else None,
    redoc_url="/redoc" if settings.TRADING_MODE != "LIVE" else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes — all API endpoints are versioned under /api/v1
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Liveness check — always returns 200 if the API process is alive.

    This endpoint is intentionally minimal (no DB/Redis probe) so that
    Docker HEALTHCHECK and container orchestrators can distinguish
    "process is running" from "dependencies are unhealthy."

    For a comprehensive dependency-level check, use GET /api/v1/health/full.
    """
    return {"status": "ok"}
