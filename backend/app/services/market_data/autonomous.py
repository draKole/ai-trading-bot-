"""Autonomous historical market-data synchronization and health state."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from app.services.market_data.provider import ProviderRegistry
from app.services.market_data.service import MarketDataService

SYMBOLS = ("ES", "MES", "NQ", "MNQ")

@dataclass
class SyncState:
    last_sync: datetime | None = None
    next_sync: datetime | None = None
    provider: str | None = None
    records: int = 0
    missing_days: list[str] = field(default_factory=list)
    duration_seconds: float | None = None
    error: str | None = None
    running: bool = False

class AutonomousMarketData:
    """Coordinates bounded, idempotent provider fetches without fabricating data."""
    def __init__(self, interval: timedelta = timedelta(hours=24)) -> None:
        self.interval = interval
        self.state = SyncState()
        self._task: asyncio.Task | None = None

    def trading_days(self, start: datetime, end: datetime) -> list[str]:
        """Return weekday dates only; exchange holidays remain explicit gaps."""
        day = start.date()
        last = end.date()
        result = []
        while day <= last:
            if day.weekday() < 5:
                result.append(day.isoformat())
            day += timedelta(days=1)
        return result

    def choose_provider(self) -> str | None:
        for name in ("yfinance", "tradovate", "databento", "csv"):
            provider = ProviderRegistry.get(name)
            if provider is not None:
                return name
        return None

    async def sync_once(self, service_factory, *, end: datetime | None = None, days: int = 1) -> dict[str, Any]:
        if self.state.running:
            return {"status": "already_running"}
        provider_name = self.choose_provider()
        if not provider_name:
            self.state.error = "No market-data provider registered"
            return {"status": "error", "error": self.state.error}
        started = datetime.now(timezone.utc)
        self.state.running = True
        self.state.provider = provider_name
        total = 0
        errors: list[str] = []
        end = end or datetime.now(timezone.utc)
        start = end - timedelta(days=max(1, days))
        self.state.missing_days = self.trading_days(start, end)
        try:
            async with service_factory() as session:
                service = MarketDataService(session)
                for symbol in SYMBOLS:
                    try:
                        result = await service.fetch_and_ingest(symbol, start, end, provider_name)
                        total += int(result.get("base_bars_fetched", 0))
                    except Exception as exc:
                        errors.append(f"{symbol}: {exc}")
                await session.commit()
            self.state.records = total
            self.state.error = "; ".join(errors) or None
            self.state.last_sync = datetime.now(timezone.utc)
            self.state.next_sync = self.state.last_sync + self.interval
            self.state.duration_seconds = (self.state.last_sync - started).total_seconds()
            return {"status": "ok" if not errors else "partial", "records": total, "errors": errors}
        finally:
            self.state.running = False

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.state.provider,
            "last_sync": self.state.last_sync.isoformat() if self.state.last_sync else None,
            "next_sync": self.state.next_sync.isoformat() if self.state.next_sync else None,
            "records": self.state.records,
            "missing_days": self.state.missing_days,
            "duration_seconds": self.state.duration_seconds,
            "error": self.state.error,
            "running": self.state.running,
        }

    async def weekly_audit(self, service_factory) -> dict[str, Any]:
        """Run a bounded seven-day integrity refresh; persistence is idempotent."""
        return await self.sync_once(service_factory, days=7)

    async def monthly_verification(self, service_factory) -> dict[str, Any]:
        """Run a bounded 31-day verification for all supported symbols."""
        return await self.sync_once(service_factory, days=31)

    async def start(self, service_factory, interval_seconds: float = 86400) -> None:
        async def loop() -> None:
            while True:
                await self.sync_once(service_factory)
                await asyncio.sleep(interval_seconds)
        self._task = asyncio.create_task(loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
