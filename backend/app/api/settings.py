"""Settings endpoints."""

from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/")
async def get_settings():
    """Return non-sensitive application settings."""
    return {
        "trading_mode": settings.TRADING_MODE,
        "data_provider": settings.DATA_PROVIDER,
        "default_risk_percent": settings.DEFAULT_RISK_PERCENT,
        "min_risk_reward": settings.DEFAULT_MIN_RISK_REWARD,
        "max_contracts": settings.MAX_CONTRACTS,
        "max_trades_per_day": settings.MAX_TRADES_PER_DAY,
        "max_trades_per_session": settings.MAX_TRADES_PER_SESSION,
    }
