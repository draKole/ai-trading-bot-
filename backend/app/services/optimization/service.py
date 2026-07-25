"""Optimization Persistence Service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, desc

from app.models.optimization import (
    OptimizationRun, OptimizationResult, ParameterSet,
    WalkForwardRun, MonteCarloRun,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class OptimizationService:
    """Persistence service for optimization."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(self, name: str, method: str = "grid") -> dict:
        r = OptimizationRun(name=name, method=method)
        self.session.add(r)
        await self.session.flush()
        return {"id": r.id, "name": r.name}

    async def get_run(self, run_id: int) -> dict | None:
        result = await self.session.execute(
            select(OptimizationRun).where(OptimizationRun.id == run_id)
        )
        r = result.scalar_one_or_none()
        if r is None:
            return None
        return {"id": r.id, "name": r.name, "method": r.method, "status": r.status,
                "total_combinations": r.total_combinations,
                "best_score": r.best_score, "best_params_json": r.best_params_json}

    async def get_runs(self, limit: int = 50) -> list[dict]:
        result = await self.session.execute(
            select(OptimizationRun).order_by(desc(OptimizationRun.created_at)).limit(limit)
        )
        return [{"id": r.id, "name": r.name, "method": r.method,
                 "status": r.status, "best_score": r.best_score}
                for r in result.scalars().all()]

    async def update_run(self, run_id: int, updates: dict) -> None:
        result = await self.session.execute(
            select(OptimizationRun).where(OptimizationRun.id == run_id)
        )
        r = result.scalar_one_or_none()
        if r:
            for k, v in updates.items():
                if hasattr(r, k):
                    setattr(r, k, v)
            await self.session.flush()
