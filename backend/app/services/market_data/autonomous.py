"""Autonomous historical market-data synchronization and health state."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
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
    last_weekly_audit: datetime | None = None
    last_monthly_verification: datetime | None = None
    retraining_required: bool = False
    retraining_reason: str | None = None
    retraining_triggered_at: datetime | None = None

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
        """Return the documented CME equity-index futures full-closure calendar.

        CME publishes holiday schedules annually; this dependency-free abstraction
        encodes the recurring full-closure dates (including observed fixed dates).
        Early-close sessions are retained because bars remain valid on those days.
        """
        end_year = year if end_year is None else end_year
        holidays: set[date] = set()
        for y in range(year, end_year + 1):
            def observed(d: date) -> date:
                return d + timedelta(days=1) if d.weekday() == 5 else d - timedelta(days=1) if d.weekday() == 6 else d
            holidays.update(observed(date(y, m, d)) for m, d in ((1, 1), (6, 19), (7, 4), (12, 25)))
            # nth weekday: weekday Monday=0; CME recurring federal closures.
            def nth(month: int, weekday: int, n: int) -> date:
                first = date(y, month, 1)
                return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
            holidays.update((nth(1, 0, 3), nth(2, 0, 3), nth(5, 0, 5), nth(9, 0, 1), nth(11, 3, 4)))
            # CME equity-index futures close Good Friday (Gregorian computus).
            a, b, c = y % 19, y // 100, y % 100
            d, e, f = b // 4, b % 4, (b + 8) // 25
            g = (b - f + 1) // 3; h = (19*a + b - d - g + 15) % 30
            i, k, l = c // 4, c % 4, (32 + 2*e + 2*i - h - k) % 7
            m = (a + 11*h + 22*l) // 451
            easter = date(y, (h + l - 7*m + 114) // 31, (h + l - 7*m + 114) % 31 + 1)
            holidays.add(easter - timedelta(days=2))
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
        """Return true at/after CME's 16:15 America/New_York post-close gate."""
        local = now.astimezone(ZoneInfo("America/New_York")) if now.tzinfo else now.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/New_York"))
        return local.time() >= time(16, 15)

    def post_close_due(self, now: datetime) -> bool:
        """Allow one regular sync per local trading date after post-close."""
        local = now.astimezone(ZoneInfo("America/New_York"))
        return self.is_post_close(now) and (self.state.last_sync is None or self.state.last_sync.astimezone(ZoneInfo("America/New_York")).date() != local.date())

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
            if errors:
                self.state.retraining_required = True
                self.state.retraining_reason = "market_data_sync_partial_failure"
                self.state.retraining_triggered_at = self.state.last_sync
            self.state.next_sync = self.state.last_sync + self.interval
            self.state.duration_seconds = (self.state.last_sync - started).total_seconds()
            return {"status": "ok" if not errors else "partial", "records": total, "errors": errors}
        finally:
            self.state.running = False

    def health(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        age_seconds = (now - self.state.last_sync).total_seconds() if self.state.last_sync else None
        stale = age_seconds is None or age_seconds > self.interval.total_seconds()
        return {
            "provider": self.state.provider,
            "status": "stale" if stale else "current",
            "stale": stale,
            "age_seconds": age_seconds,
            "last_sync": self.state.last_sync.isoformat() if self.state.last_sync else None,
            "next_sync": self.state.next_sync.isoformat() if self.state.next_sync else None,
            "records": self.state.records,
            "missing_days": self.state.missing_days,
            "duration_seconds": self.state.duration_seconds,
            "error": self.state.error,
            "running": self.state.running,
            "scheduler_started": self._task is not None and not self._task.done(),
            "last_weekly_audit": self.state.last_weekly_audit.isoformat() if self.state.last_weekly_audit else None,
            "last_monthly_verification": self.state.last_monthly_verification.isoformat() if self.state.last_monthly_verification else None,
            "retraining_required": self.state.retraining_required,
            "retraining_reason": self.state.retraining_reason,
            "retraining_triggered_at": self.state.retraining_triggered_at.isoformat() if self.state.retraining_triggered_at else None,
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
                if self.post_close_due(now):
                    await self.sync_once(service_factory)
                if now - weekly_at >= timedelta(days=7):
                    await self.weekly_audit(service_factory); weekly_at = now
                    self.state.last_weekly_audit = now
                if now - monthly_at >= timedelta(days=30):
                    await self.monthly_verification(service_factory); monthly_at = now
                    self.state.last_monthly_verification = now
                await asyncio.sleep(interval_seconds)
        self._task = asyncio.create_task(loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
