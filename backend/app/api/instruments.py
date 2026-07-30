"""Instrument endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.market_data import MarketDataService

router = APIRouter()


def get_market_data_service(
    db: AsyncSession = Depends(get_db),
) -> MarketDataService:
    return MarketDataService(db)


@router.get("/")
async def list_instruments(
    exchange: str | None = Query(None, description="Filter by exchange (e.g. CME)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    service: MarketDataService = Depends(get_market_data_service),
):
    """List available trading instruments with optional filtering and pagination."""
    instruments = await service.list_instruments()

    if exchange:
        instruments = [i for i in instruments if i.exchange == exchange.upper()]

    total = len(instruments)
    start = (page - 1) * page_size
    page_items = instruments[start:start + page_size]

    return {
        "instruments": [
            {
                "id": i.id,
                "symbol": i.symbol,
                "name": i.name,
                "exchange": i.exchange,
                "tick_size": i.tick_size,
                "tick_value": i.tick_value,
                "multiplier": i.multiplier,
                "min_contracts": i.min_contracts,
                "max_contracts": i.max_contracts,
                "is_active": i.is_active,
            }
            for i in page_items
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        },
    }


@router.get("/{symbol}")
async def get_instrument_by_symbol(
    symbol: str,
    service: MarketDataService = Depends(get_market_data_service),
):
    """Get a single instrument by its symbol (e.g. ES, NQ, MNQ)."""
    instrument = await service.get_instrument_by_symbol(symbol.upper())
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"Instrument '{symbol}' not found")
    return {
        "id": instrument.id,
        "symbol": instrument.symbol,
        "name": instrument.name,
        "exchange": instrument.exchange,
        "tick_size": instrument.tick_size,
        "tick_value": instrument.tick_value,
        "multiplier": instrument.multiplier,
        "min_contracts": instrument.min_contracts,
        "max_contracts": instrument.max_contracts,
        "is_active": instrument.is_active,
        "created_at": instrument.created_at.isoformat() if instrument.created_at else None,
    }
