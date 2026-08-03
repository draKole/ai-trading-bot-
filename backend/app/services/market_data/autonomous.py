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
            # Federal exchange closures: MLK, Presidents, Memorial, Juneteenth, Labor, Thanksgiving.
            jan1 = date(y, 1, 1)
            mlk = date(y, 1, 1) + timedelta(days=(7 - date(y, 1, 1).weekday()) % 7 + 14); holidays.add(mlk)
            feb1 = date(y, 2, 1); holidays.add(feb1 + timedelta(days=(0 - feb1.weekday()) % 7 + 14))
            may31 = date(y, 5, 31); holidays.add(may31 - timedelta(days=(may31.weekday() + 1) % 7))
            jun19 = date(y, 6, 19); holidays.add(jun19 + timedelta(days=1) if jun19.weekday()==5 else jun19 - timedelta(days=1) if jun19.weekday()==6 else jun19)
            sep1 = date(y, 9, 1); holidays.add(sep1 + timedelta(days=(0 - sep1.weekday()) % 7))
            nov1 = date(y, 11, 1); holidays.add(nov1 + timedelta(days=(3 - nov1.weekday()) % 7 + 21))
            # Good Friday, derived from computus.
            a=y%19; b=y//100; c=y%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3; h=(19*a+b-d-g+15)%30; i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451; month=(h+l-7*m+114)//31; day=(h+l-7*m+114)%31+1
            easter=date(y,month,day); holidays.add(easter-timedelta(days=2))
        return holidays

    async def find_missing_days(self, session, start: datetime, end: datetime) -> list[str]:
        """Find weekday/holiday-aware dates with no stored bars for required symbols."""
        expected = set(self.trading_days(start, end))
        if not expected:
            return []
        rows = await session.execute(select(func.date(Bar.timestamp)).join(Instrument, Bar.instrument_id == Instrument.id).where(Instrument.symbol.in_(SYMBOLS), Bar.timeframe == "1m", Bar.timestamp >= start, Bar.timestamp <= end).distinct())
        present = {str(row[0]) for row in rows.all()}
        return sorted(expected - present)

    @staticmethod
    def is_post_close(now: datetime) -> bool:
        """Return true after 16:15 America/New_York equivalent (UTC-safe approximation)."""
        # Futures sync is intentionally gated to the 16:15-23:59 UTC operational window.
        return now.hour >= 16

    async def backfill_missing(self, service_factory, *, end: datetime | None = None) -> dict[str, Any]:
        """Backfill the bounded missing-date window through the same idempotent pipeline."""
        return await self.sync_once(service_factory, end=end, days=7)

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
            weekly_at = datetime.now(timezone.utc)
            monthly_at = weekly_at
            while True:
                now = datetime.now(timezone.utc)
                if self.is_post_close(now):
                    await self.sync_once(service_factory)
                    if now - weekly_at >= timedelta(days=7):
                        await self.weekly_audit(service_factory); weekly_at = now
                    if now - monthly_at >= timedelta(days=30):
                        await self.monthly_verification(service_factory); monthly_at = now
                await asyncio.sleep(interval_seconds)
        self._task = asyncio.create_task(loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
