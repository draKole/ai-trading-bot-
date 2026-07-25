"""Scanner Persistence Service."""

from __future__ import annotations
from typing import TYPE_CHECKING
import structlog
from sqlalchemy import select, desc
from app.models.scanner import Watchlist, WatchlistSymbol, ScanRun, ScanResult, Opportunity

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class ScannerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_watchlist(self, name: str, description: str = "") -> dict:
        w = Watchlist(name=name, description=description)
        self.session.add(w); await self.session.flush()
        return {"id": w.id, "name": w.name}

    async def get_watchlists(self) -> list[dict]:
        result = await self.session.execute(select(Watchlist))
        return [{"id": w.id, "name": w.name, "description": w.description}
                for w in result.scalars().all()]

    async def create_scan(self, watchlist_id: int) -> dict:
        s = ScanRun(watchlist_id=watchlist_id, status="running")
        self.session.add(s); await self.session.flush()
        return {"id": s.id, "status": s.status}

    async def update_scan(self, scan_id: int, updates: dict):
        r = await self.session.execute(select(ScanRun).where(ScanRun.id == scan_id))
        s = r.scalar_one_or_none()
        if s:
            for k, v in updates.items():
                if hasattr(s, k): setattr(s, k, v)
            await self.session.flush()

    async def get_scans(self, limit: int = 50) -> list[dict]:
        result = await self.session.execute(select(ScanRun).order_by(desc(ScanRun.created_at)).limit(limit))
        return [{"id": s.id, "status": s.status, "symbols_scanned": s.symbols_scanned,
                 "opportunities_found": s.opportunities_found, "duration_ms": s.duration_ms}
                for s in result.scalars().all()]
