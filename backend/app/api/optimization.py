"""Optimization API — grid search, random, walk-forward, Monte Carlo, comparison."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.optimization import (
    OptimizationService, OptimizationController, ParamRange,
    monte_carlo_simulation, compare_strategies,
)

router = APIRouter()

_controller = OptimizationController()


@router.get("/runs")
async def list_runs(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = OptimizationService(db)
    runs = await service.get_runs(limit=limit)
    return {"count": len(runs), "runs": runs}


@router.get("/runs/{run_id}")
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = OptimizationService(db)
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"Run not found: {run_id}")
    return run


@router.post("/grid-search")
async def run_grid_search(
    param_ranges_json: str = Query(..., description="JSON: [{\"name\":\"min_rr\",\"min\":2,\"max\":4,\"step\":0.5}]"),
    db: AsyncSession = Depends(get_db),
):
    ranges_raw = json.loads(param_ranges_json)
    ranges = [ParamRange(**r) for r in ranges_raw]
    run = _controller.run_grid_search(ranges)
    service = OptimizationService(db)
    db_run = await service.create_run(run["name"], "grid")
    await service.update_run(db_run["id"], {
        "status": run["status"],
        "total_combinations": run["total_combinations"],
        "completed_combinations": run["completed_combinations"],
        "best_score": run["best_score"],
        "best_params_json": json.dumps(run.get("best_params")),
    })
    return {
        "run_id": db_run["id"],
        "combinations": run["total_combinations"],
        "best_score": run["best_score"],
        "best_params": run.get("best_params"),
    }


@router.post("/monte-carlo")
async def run_monte_carlo(
    trades_json: str = Query("[]", description="JSON array of trade dicts"),
    iterations: int = Query(1000, le=10000),
    seed: int = Query(42),
    db: AsyncSession = Depends(get_db),
):
    trades = json.loads(trades_json)
    result = _controller.run_monte_carlo(trades, iterations, seed)
    service = OptimizationService(db)
    return result


@router.post("/compare")
async def compare_results(
    results_json: str = Query(..., description="JSON array of {params, metrics}"),
    db: AsyncSession = Depends(get_db),
):
    results = json.loads(results_json)
    comparison = compare_strategies(results)
    return comparison


@router.get("/statistics")
async def get_statistics():
    return {"total_runs": len(_controller.list_runs())}
