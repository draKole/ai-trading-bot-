"""Autonomous historical market-data synchronization and health state."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import func, select
from app.models.bar import Bar
from app.models.instrument import Instrument
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
        """Return weekdays excluding observed US market holidays."""
        day = start.date()
        last = end.date()
        result = []
        while day <= last:
            if day.weekday() < 5 and day not in self.market_holidays(day.year, day.year + 1):
                result.append(day.isoformat())
            day += timedelta(days=1)
        return result

    @staticmethod
    def market_holidays(year: int, end_year: int | None = None) -> set[date]:
        """Return conservative observed US exchange holidays (no fabricated bars)."""
        end_year = end_year or year
        holidays: set[date] = set()
        for y in range(year, end_year + 1):
            fixed = ((1, 1), (7, 4), (12, 25))
            for month, day in fixed:
                d = date(y, month, day)
                holidays.add(d + timedelta(days=1) if d.weekday() == 5 else d - timedelta(days=1) if d.weekday() == 6 else d)
            # Memorial/Thanksgiving approximations using calendar arithmetic.
            may31 = date(y, 5, 31); holidays.add(may31 - timedelta(days=(may31.weekday() + 1) % 7))
            nov1 = date(y, 11, 1); fourth = nov1 + timedelta(days=(3 - nov1.weekday()) % 7 + 21); holidays.add(fourth)
        return holidays

    async def find_missing_days(self, session, start: datetime, end: datetime) -> list[str]:
        """Find weekday/holiday-aware dates with no stored bars for required symbols."""
        expected = set(self.trading_days(start, end))
        if not expected:
            return []
        rows = await session.execute(select(func.date(Bar.timestamp)).join(Instrument, Bar.instrument_id == Instrument.id).where(Instrument.symbol.in_(SYMBOLS), Bar.timeframe == "1m", Bar.timestamp >= start, Bar.timestamp <= end).distinct())
        present = {str(row[0]) for row in rows.all()}
        return sorted(expected - present)

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
                self.state.missing_days = await self.find_missing_days(session, start, end)
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
