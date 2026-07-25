"""Scanner API — watchlists, scan, opportunities, rankings."""

from __future__ import annotations
from typing import Optional
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.scanner import ScannerService, ScannerController, score_opportunity

router = APIRouter()
_controller = ScannerController()


@router.get("/watchlists")
async def list_watchlists(db: AsyncSession = Depends(get_db)):
    service = ScannerService(db)
    wls = await service.get_watchlists()
    return {"count": len(wls), "watchlists": wls}


@router.post("/watchlists/create")
async def create_watchlist(
    name: str = Query(...), description: str = Query(""),
    symbols_json: str = Query("[]"),
    timeframes_json: str = Query('["5m"]'),
    db: AsyncSession = Depends(get_db),
):
    symbols = json.loads(symbols_json)
    timeframes = json.loads(timeframes_json)
    _controller.create_watchlist(name, symbols, timeframes, description)
    service = ScannerService(db)
    wl = await service.create_watchlist(name, description)
    return {"id": wl["id"], "name": name, "symbol_count": len(symbols)}


@router.post("/scan")
async def run_scan(
    watchlist: str = Query(...),
    market_data_json: str = Query("{}"),
    db: AsyncSession = Depends(get_db),
):
    data = json.loads(market_data_json) if market_data_json else {}
    results = _controller.scan(watchlist, data)
    return {"watchlist": watchlist, "count": len(results),
            "opportunities": [r.to_dict() for r in results[:50]]}


@router.get("/scan/top")
async def get_top(
    watchlist: str = Query(...), top_n: int = Query(10, le=100),
    db: AsyncSession = Depends(get_db),
):
    results = _controller.get_top_opportunities(watchlist, top_n)
    return {"top": [r.to_dict() for r in results]}


@router.get("/scans")
async def list_scans(limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    service = ScannerService(db)
    scans = await service.get_scans(limit=limit)
    return {"count": len(scans), "scans": scans}


@router.get("/statistics")
async def get_statistics():
    return _controller.get_statistics()
