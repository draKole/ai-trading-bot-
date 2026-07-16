"""Instrument endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.market_data import MarketDataService

router = APIRouter()


@router.get("/")
async def list_instruments(
    db: AsyncSession = Depends(get_db),
):
    """List available trading instruments."""
    service = MarketDataService(db)
    instruments = await service.list_instruments()
    return {
        "instruments": [
            {
                "symbol": i.symbol,
                "name": i.name,
                "exchange": i.exchange,
                "tick_size": i.tick_size,
                "tick_value": i.tick_value,
                "multiplier": i.multiplier,
            }
            for i in instruments
        ]
    }
