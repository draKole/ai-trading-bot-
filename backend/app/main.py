"""Drake AI Trading — FastAPI Application Entry Point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import check_db_connection
from app.core.redis import check_redis_connection, close_redis
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle handler."""
    # Startup
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    if not db_ok:
        print("WARNING: Database connection failed on startup")
    if not redis_ok:
        print("WARNING: Redis connection failed on startup")
    print(f"Drake AI Trading started in {settings.TRADING_MODE} mode")
    if settings.TRADING_MODE == "LIVE" and not settings.LIVE_ALLOWED:
        raise RuntimeError("LIVE mode is not allowed — set LIVE_ALLOWED=true")
    yield
    # Shutdown
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

# Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "mode": settings.TRADING_MODE,
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
    }
