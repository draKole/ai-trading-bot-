"""API Router — aggregates all resource routers."""

from fastapi import APIRouter

from app.api import (
    health,
    auth,
    instruments,
    market_data,
    signals,
    trades,
    backtesting,
    analytics,
    dashboard,
    risk,
    settings as settings_router,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(instruments.router, prefix="/instruments", tags=["Instruments"])
api_router.include_router(market_data.router, prefix="/market-data", tags=["Market Data"])
api_router.include_router(signals.router, prefix="/signals", tags=["Signals"])
api_router.include_router(trades.router, prefix="/trades", tags=["Trades"])
api_router.include_router(backtesting.router, prefix="/backtesting", tags=["Backtesting"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk"])
api_router.include_router(settings_router.router, prefix="/settings", tags=["Settings"])
