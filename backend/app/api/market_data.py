"""Market Data API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Body
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.services.market_data.autonomous import AutonomousMarketData
from app.services.market_data import (
    MarketDataService,
    VALID_TIMEFRAMES,
    ProviderRegistry,
)

logger = structlog.get_logger()
router = APIRouter()
autonomous_sync = AutonomousMarketData()


def get_market_data_service(
    db: AsyncSession = Depends(get_db),
) -> MarketDataService:
    return MarketDataService(db)


# ─── Common bar serialization ─────────────────────────────────

def _parse_iso_datetime(value: str, field_name: str) -> datetime:
    """Parse an API datetime and normalize naive values to UTC."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}. Use an ISO-8601 date or datetime.",
        ) from exc
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _serialize_bar(b) -> dict:
    """Serialize a Bar ORM object to a dict for API response."""
    return {
        "timestamp": b.timestamp.isoformat(),
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
        "volume": b.volume,
        "vwap": b.vwap,
        "session": b.session,
        "provider": b.provider,
    }


# ─── Instruments ─────────────────────────────────────────────

@router.get("/autonomous/health")
async def autonomous_health():
    """Expose synchronization state for operational monitoring."""
    return autonomous_sync.health()

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
    session: Optional[str] = Query(None, description="Filter by session (RTH, ETH, Asian, London, full)"),
    limit: int = Query(5000, ge=1, le=100000),
    service: MarketDataService = Depends(get_market_data_service),
):
    """Retrieve stored OHLCV bars with optional session filter."""
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Must be one of: {VALID_TIMEFRAMES}",
        )

    start_dt = _parse_iso_datetime(start, "start") if start else None
    end_dt = _parse_iso_datetime(end, "end") if end else None
    if start_dt and end_dt and end_dt < start_dt:
        raise HTTPException(status_code=400, detail="end must not be earlier than start")

    bars = await service.query_bars(
        instrument=instrument.upper(),
        timeframe=timeframe,
        start=start_dt,
        end=end_dt,
        session=session,
        limit=limit,
    )

    return {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "session": session,
        "count": len(bars),
        "bars": [_serialize_bar(b) for b in bars],
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


@router.get("/bars/latest")
async def get_latest_bar(
    instrument: str = Query(..., description="Instrument symbol"),
    timeframe: str = Query("1m", description="Timeframe"),
    service: MarketDataService = Depends(get_market_data_service),
):
    """Get the most recent bar for an instrument/timeframe."""
    bar = await service.get_latest_bar(instrument.upper(), timeframe)
    if bar is None:
        raise HTTPException(
            status_code=404,
            detail=f"No bars found for {instrument.upper()} {timeframe}",
        )
    return {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "bar": _serialize_bar(bar),
    }


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
    start_dt = _parse_iso_datetime(start, "start")
    end_dt = _parse_iso_datetime(end, "end")
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="end must be later than start")

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


@router.post("/import")
async def import_bars_json(
    bars: list[dict] = Body(..., description="List of OHLCV bar objects"),
    service: MarketDataService = Depends(get_market_data_service),
):
    """Import OHLCV bars from a JSON body.

    Each bar dict should have: instrument, timeframe, timestamp, open, high,
    low, close, volume, and optionally vwap, session, provider.
    """
    if not bars:
        raise HTTPException(status_code=400, detail="No bars provided")

    try:
        return await service.import_bars(bars)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ingest/csv")
async def ingest_csv(
    instrument: str = Query(...),
    timeframe: str = Query("1m"),
    file: UploadFile = File(...),
    service: MarketDataService = Depends(get_market_data_service),
):
    """Upload a CSV file of OHLCV bars for ingestion."""
    from app.services.market_data.csv_provider import CSVProvider

    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {timeframe}")

    import os
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        provider = CSVProvider(
            default_instrument=instrument.upper(),
            default_timeframe=timeframe,
        )
        parsed = provider.load_file_with_report(tmp_path)
        result = await service.ingest_bars(parsed.bars)
        result["submitted"] = len(parsed.bars) + len(parsed.errors)
        result["invalid"] += len(parsed.errors)
        result["invalid_rows"] = parsed.errors[:25] + result["invalid_rows"]
        result["parse_errors"] = len(parsed.errors)
        return {
            "file": file.filename,
            "instrument": instrument.upper(),
            "timeframe": timeframe,
            **result,
        }
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"CSV import failed: {exc}") from exc
    finally:
        os.unlink(tmp_path)


# ─── Providers ───────────────────────────────────────────────

@router.get("/providers")
async def list_providers():
    """List available data providers."""
    return {"providers": ProviderRegistry.list_providers()}
