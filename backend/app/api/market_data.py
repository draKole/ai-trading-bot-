"""Market Data API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.services.market_data import (
    MarketDataService,
    VALID_TIMEFRAMES,
    ProviderRegistry,
)

logger = structlog.get_logger()
router = APIRouter()


def get_market_data_service(
    db: AsyncSession = Depends(get_db),
) -> MarketDataService:
    return MarketDataService(db)


# ─── Instruments ─────────────────────────────────────────────

@router.get("/instruments")
async def list_instruments(
    service: MarketDataService = Depends(get_market_data_service),
):
    """List all available trading instruments."""
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


# ─── Bars ────────────────────────────────────────────────────

@router.get("/bars")
async def get_bars(
    instrument: str = Query(..., description="Instrument symbol (MNQ, NQ, MES, ES)"),
    timeframe: str = Query(..., description=f"Timeframe: {', '.join(VALID_TIMEFRAMES)}"),
    start: Optional[str] = Query(None, description="Start datetime (ISO format)"),
    end: Optional[str] = Query(None, description="End datetime (ISO format)"),
    limit: int = Query(5000, ge=1, le=100000),
    service: MarketDataService = Depends(get_market_data_service),
):
    """Retrieve stored OHLCV bars."""
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Must be one of: {VALID_TIMEFRAMES}",
        )

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    bars = await service.get_bars(
        instrument=instrument.upper(),
        timeframe=timeframe,
        start=start_dt,
        end=end_dt,
        limit=limit,
    )

    return {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "count": len(bars),
        "bars": [
            {
                "timestamp": b.timestamp.isoformat(),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "provider": b.provider,
            }
            for b in bars
        ],
    }


@router.get("/bars/count")
async def get_bar_count(
    instrument: str = Query(...),
    timeframe: str = Query(...),
    service: MarketDataService = Depends(get_market_data_service),
):
    """Count stored bars for an instrument/timeframe."""
    count = await service.get_bar_count(instrument.upper(), timeframe)
    return {"instrument": instrument.upper(), "timeframe": timeframe, "count": count}


# ─── Timeframes ──────────────────────────────────────────────

@router.get("/timeframes")
async def list_timeframes(
    instrument: str = Query(...),
    service: MarketDataService = Depends(get_market_data_service),
):
    """List timeframes that have data for a given instrument."""
    tfs = await service.get_available_timeframes(instrument.upper())
    return {"instrument": instrument.upper(), "available_timeframes": tfs}


# ─── Data Import ─────────────────────────────────────────────

@router.post("/ingest/fetch")
async def fetch_and_ingest(
    instrument: str = Query(..., description="Instrument symbol"),
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    provider: str = Query("yfinance", description="Data provider name"),
    service: MarketDataService = Depends(get_market_data_service),
):
    """Fetch data from a provider, aggregate all timeframes, and store."""
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use ISO format (YYYY-MM-DD).",
        )

    try:
        result = await service.fetch_and_ingest(
            instrument=instrument.upper(),
            start=start_dt,
            end=end_dt,
            provider_name=provider,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("ingest_fetch_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@router.post("/ingest/csv")
async def ingest_csv(
    instrument: str = Query(...),
    timeframe: str = Query("1m"),
    file: UploadFile = File(...),
    service: MarketDataService = Depends(get_market_data_service),
):
    """Upload a CSV file of OHLCV bars for ingestion."""
    from app.services.market_data.csv_provider import CSVProvider

    # Save temp file
    import tempfile, os
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv", mode="w",
    ) as tmp:
        content = await file.read()
        tmp.write(content.decode("utf-8"))
        tmp_path = tmp.name

    try:
        provider = CSVProvider(
            default_instrument=instrument.upper(),
            default_timeframe=timeframe,
        )
        bars = provider.load_file(tmp_path)
        result = await service.ingest_bars(bars)
        return {
            "file": file.filename,
            "instrument": instrument.upper(),
            "timeframe": timeframe,
            **result,
        }
    finally:
        os.unlink(tmp_path)


# ─── Providers ───────────────────────────────────────────────

@router.get("/providers")
async def list_providers():
    """List available data providers."""
    return {"providers": ProviderRegistry.list_providers()}
