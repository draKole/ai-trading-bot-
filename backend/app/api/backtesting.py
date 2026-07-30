"""Backtesting API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.backtesting import (
    BacktestingService, BacktestController, BacktestConfig,
    ParamSweepConfig, compute_metrics,
)

router = APIRouter()


# ─── Runs ──────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(
    instrument: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List backtest runs."""
    service = BacktestingService(db)
    runs = await service.get_runs(instrument=instrument, status=status, limit=limit)
    return {"count": len(runs), "runs": runs}


@router.get("/runs/{run_id}")
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a backtest run by ID."""
    service = BacktestingService(db)
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"Run not found: {run_id}")
    return run


@router.post("/run")
async def run_backtest(
    instrument: str = Query(...),
    timeframe: str = Query("5m"),
    start_time: str = Query(...),
    end_time: str = Query(...),
    strategy: str = Query("trend_following"),
    bars_json: str = Query(..., description="JSON array of OHLCV bars"),
    initial_balance: float = Query(100_000.0),
    commission: float = Query(2.50),
    slippage: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Run a backtest and persist results."""
    service = BacktestingService(db)

    st = datetime.fromisoformat(start_time)
    et = datetime.fromisoformat(end_time)

    config = BacktestConfig(
        instrument=instrument.upper(),
        timeframe=timeframe,
        start_time=st,
        end_time=et,
        strategy=strategy,
        initial_balance=initial_balance,
        commission_per_contract=commission,
        slippage_ticks=slippage,
    )

    # Create run record
    run_data = await service.create_run({
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "start_time": st,
        "end_time": et,
    })
    run_id = run_data["id"]

    # Parse bars and run backtest
    bar_dicts = json.loads(bars_json)
    controller = BacktestController(config)
    result = controller.run(bar_dicts)

    # Persist trades, metrics, equity curve
    trade_dicts = [t.to_dict() for t in result.trades]
    if trade_dicts:
        await service.store_trades_bulk(run_id, trade_dicts)

    metrics_dict = result.metrics.to_dict()
    await service.store_metrics(run_id, metrics_dict)

    equity_dicts = [e.to_dict() for e in result.equity_curve]

    import json as _json
    await service.update_run(run_id, {
        "status": "completed",
        "total_bars": len(bar_dicts),
        "metrics_json": _json.dumps(metrics_dict),
        "equity_curve_json": _json.dumps(equity_dicts),
    })

    return {
        "run_id": run_id,
        "status": "completed",
        "metrics": metrics_dict,
        "trade_count": len(trade_dicts),
        "equity_curve": equity_dicts,
    }


@router.post("/run-dry")
async def run_dry_backtest(
    instrument: str = Query("ES"),
    timeframe: str = Query("5m"),
    start_time: str = Query("2025-06-16T09:30:00"),
    end_time: str = Query("2025-06-16T16:00:00"),
    strategy: str = Query("trend_following"),
    bars_json: str = Query(..., description="JSON array of OHLCV bars"),
    initial_balance: float = Query(100_000.0),
    commission: float = Query(2.50),
    slippage: int = Query(1),
):
    """Run a backtest without persistence (dry-run)."""
    st = datetime.fromisoformat(start_time)
    et = datetime.fromisoformat(end_time)

    config = BacktestConfig(
        instrument=instrument.upper(),
        timeframe=timeframe,
        start_time=st,
        end_time=et,
        strategy=strategy,
        initial_balance=initial_balance,
        commission_per_contract=commission,
        slippage_ticks=slippage,
    )

    bar_dicts = json.loads(bars_json)
    controller = BacktestController(config)
    result = controller.run(bar_dicts)

    return result.to_dict()


@router.get("/runs/{run_id}/trades")
async def get_run_trades(
    run_id: int,
    limit: int = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Get trades for a backtest run."""
    service = BacktestingService(db)
    trades = await service.get_trades(run_id=run_id, limit=limit)
    return {"run_id": run_id, "count": len(trades), "trades": trades}


@router.get("/runs/{run_id}/metrics")
async def get_run_metrics(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get metrics for a backtest run."""
    service = BacktestingService(db)
    metrics = await service.get_metrics(run_id)
    if metrics is None:
        raise HTTPException(404, f"Metrics not found for run: {run_id}")
    return {"run_id": run_id, "metrics": metrics}


@router.get("/statistics")
async def get_statistics(
    instrument: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get backtesting statistics for an instrument."""
    service = BacktestingService(db)
    return await service.get_statistics(instrument=instrument)


# ─── Parameter Sweeps ─────────────────────────────────────

@router.post("/sweep")
async def run_parameter_sweep(
    instrument: str = Query("ES"),
    timeframe: str = Query("5m"),
    start_time: str = Query("2025-06-16T09:30:00"),
    end_time: str = Query("2025-06-16T16:00:00"),
    bars_json: str = Query(..., description="JSON array of OHLCV bars"),
    param_grid_json: str = Query("{}", description='JSON dict of param → [values]'),
    initial_balance: float = Query(100_000.0),
):
    """Run a parameter sweep — one backtest per parameter combination."""
    st = datetime.fromisoformat(start_time)
    et = datetime.fromisoformat(end_time)

    param_grid = json.loads(param_grid_json)
    bar_dicts = json.loads(bars_json)

    sweep = ParamSweepConfig(
        instrument=instrument.upper(),
        timeframe=timeframe,
        start_time=st,
        end_time=et,
        base_config={"initial_balance": initial_balance},
        param_grid=param_grid,
    )

    controller = BacktestController()
    results = controller.run_parameter_sweep(bar_dicts, sweep)

    return {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "combinations": len(results),
        "results": [
            {
                "config": r.config.to_dict(),
                "metrics": r.metrics.to_dict(),
                "trade_count": len(r.trades),
            }
            for r in results
        ],
    }
