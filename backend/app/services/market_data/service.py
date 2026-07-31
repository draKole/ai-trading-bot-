"""Market Data Service — orchestrate data ingestion, storage, and retrieval."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select, text

from app.services.market_data.provider import (
    OHLCVBar,
    ProviderRegistry,
)
from app.services.market_data.aggregator import BarAggregator
from app.services.market_data.validator import BarValidator, detect_overlapping_bars
from app.models.instrument import Instrument, DEFAULT_INSTRUMENTS
from app.models.bar import Bar

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class MarketDataService:
    """Primary service for market-data ingestion, storage, and retrieval."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ─── Instrument Management ───────────────────────────────

    async def seed_instruments(self) -> list[Instrument]:
        """Ensure default instruments exist in the database."""
        existing = await self.list_instruments()
        existing_symbols = {item.symbol for item in existing}
        new_instruments: list[Instrument] = []
        for spec in DEFAULT_INSTRUMENTS:
            if spec["symbol"] not in existing_symbols:
                instrument = Instrument(**spec)
                self.session.add(instrument)
                new_instruments.append(instrument)
        if new_instruments:
            await self.session.flush()
            logger.info("instruments_seeded", count=len(new_instruments))
        return new_instruments

    async def list_instruments(self) -> list[Instrument]:
        result = await self.session.execute(
            select(Instrument)
            .where(Instrument.is_active == True)  # noqa: E712
            .order_by(Instrument.symbol)
        )
        return list(result.scalars().all())

    async def get_instrument_by_symbol(self, symbol: str) -> Instrument | None:
        result = await self.session.execute(
            select(Instrument).where(Instrument.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()

    # ─── Data Ingestion ──────────────────────────────────────

    async def ingest_bars(self, bars: list[OHLCVBar]) -> dict[str, Any]:
        """Validate, deduplicate, and persist a batch of canonical bars.

        Imports are idempotent for the database unique key
        ``(instrument, timeframe, timestamp, provider)``. Validation failures
        are reported in the response and do not prevent independent valid rows
        in the same upload from being stored.
        """
        validation = BarValidator.validate_and_deduplicate(bars)
        await self.seed_instruments()

        instrument_cache: dict[str, int] = {}
        recognized_bars: list[OHLCVBar] = []
        unknown_symbols: set[str] = set()
        for bar in validation.valid_bars:
            if bar.instrument not in instrument_cache:
                instrument = await self.get_instrument_by_symbol(bar.instrument)
                if instrument is None:
                    unknown_symbols.add(bar.instrument)
                    continue
                instrument_cache[bar.instrument] = instrument.id
            recognized_bars.append(bar)

        existing = await self._get_existing_bars_for_check(recognized_bars)
        new_bars = detect_overlapping_bars(existing, recognized_bars)

        for bar in new_bars:
            self.session.add(Bar(
                instrument_id=instrument_cache[bar.instrument],
                timeframe=bar.timeframe,
                timestamp=bar.timestamp,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                vwap=bar.vwap,
                session=bar.session,
                provider=bar.provider,
                ingested_at=datetime.utcnow(),
            ))
        await self.session.flush()

        invalid_details = [
            {"instrument": bar.instrument, "timestamp": _timestamp_text(bar.timestamp), "errors": errors}
            for bar, errors in validation.invalid_bars[:25]
        ]
        return {
            "submitted": len(bars),
            "valid": len(validation.valid_bars),
            "accepted": len(recognized_bars),
            "inserted": len(new_bars),
            "duplicates_in_batch": len(validation.duplicates),
            "duplicates_in_db": len(recognized_bars) - len(new_bars),
            "invalid": len(validation.invalid_bars),
            "invalid_rows": invalid_details,
            "unknown_instruments": sorted(unknown_symbols),
            "skipped_unknown_instrument": sum(
                1 for bar in validation.valid_bars if bar.instrument in unknown_symbols
            ),
            "gaps_detected": len(validation.gaps),
            "gaps": validation.gaps[:10],
        }

    async def _get_existing_bars_for_check(self, bars: list[OHLCVBar]) -> list[OHLCVBar]:
        """Load already-stored bars for every identity series in an import.

        The old implementation inspected only the first bar's series and also
        dropped its instrument while building overlap keys.  Both flaws made
        mixed imports non-idempotent and could cause a uniqueness failure on
        retry.
        """
        by_series: dict[tuple[str, str, str], list[OHLCVBar]] = defaultdict(list)
        for bar in bars:
            by_series[(bar.instrument, bar.timeframe, bar.provider)].append(bar)

        existing: list[OHLCVBar] = []
        for (instrument_symbol, timeframe, provider), series_bars in by_series.items():
            instrument = await self.get_instrument_by_symbol(instrument_symbol)
            if instrument is None:
                continue
            min_timestamp = min(bar.timestamp for bar in series_bars)
            max_timestamp = max(bar.timestamp for bar in series_bars)
            result = await self.session.execute(
                select(Bar).where(
                    Bar.instrument_id == instrument.id,
                    Bar.timeframe == timeframe,
                    Bar.provider == provider,
                    Bar.timestamp >= min_timestamp,
                    Bar.timestamp <= max_timestamp,
                )
            )
            existing.extend(
                self._bar_to_ohclv(db_bar, instrument_symbol)
                for db_bar in result.scalars().all()
            )
        return existing

    @staticmethod
    def _bar_to_ohclv(db_bar: Bar, instrument: str) -> OHLCVBar:
        return OHLCVBar(
            instrument=instrument,
            timeframe=db_bar.timeframe,
            timestamp=db_bar.timestamp,
            open=db_bar.open,
            high=db_bar.high,
            low=db_bar.low,
            close=db_bar.close,
            volume=db_bar.volume,
            provider=db_bar.provider,
            vwap=db_bar.vwap,
            session=db_bar.session,
        )

    async def import_bars(self, bars: list[dict[str, Any]]) -> dict[str, Any]:
        """Parse and import JSON bars without trusting request payload types."""
        canonical_bars: list[OHLCVBar] = []
        parse_errors: list[dict[str, Any]] = []
        for row_number, bar_data in enumerate(bars, start=1):
            try:
                if not isinstance(bar_data, dict):
                    raise ValueError("bar must be an object")
                canonical_bars.append(OHLCVBar.from_dict(bar_data))
            except (TypeError, ValueError) as exc:
                parse_errors.append({"row": row_number, "errors": [str(exc)]})

        result = await self.ingest_bars(canonical_bars)
        result["submitted"] = len(bars)
        result["invalid"] += len(parse_errors)
        result["invalid_rows"] = parse_errors[:25] + result["invalid_rows"]
        result["parse_errors"] = len(parse_errors)
        return result

    # ─── Data Retrieval ──────────────────────────────────────

    async def get_bars(
        self,
        instrument: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 5000,
    ) -> list[Bar]:
        instrument_model = await self.get_instrument_by_symbol(instrument)
        if instrument_model is None:
            return []
        conditions = [Bar.instrument_id == instrument_model.id, Bar.timeframe == timeframe]
        if start:
            conditions.append(Bar.timestamp >= start)
        if end:
            conditions.append(Bar.timestamp <= end)
        result = await self.session.execute(
            select(Bar).where(*conditions).order_by(Bar.timestamp.asc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_available_timeframes(self, instrument: str) -> list[str]:
        instrument_model = await self.get_instrument_by_symbol(instrument)
        if instrument_model is None:
            return []
        result = await self.session.execute(
            select(Bar.timeframe)
            .where(Bar.instrument_id == instrument_model.id)
            .distinct()
            .order_by(Bar.timeframe)
        )
        return [row[0] for row in result.all()]

    # ─── Provider Fetch Pipeline ─────────────────────────────

    async def fetch_and_ingest(
        self,
        instrument: str,
        start: datetime,
        end: datetime,
        provider_name: str = "yfinance",
    ) -> dict[str, Any]:
        """Fetch 1-minute bars, build chart timeframes, validate, and store."""
        if end <= start:
            raise ValueError("end must be later than start")
        provider = ProviderRegistry.get(provider_name)
        if provider is None:
            raise ValueError(f"Unknown provider: {provider_name}")
        if not await provider.is_available():
            raise ValueError(f"Provider is unavailable: {provider_name}")

        await self.seed_instruments()
        if await self.get_instrument_by_symbol(instrument) is None:
            raise ValueError(f"Unsupported instrument: {instrument}")

        logger.info(
            "fetching_data", instrument=instrument, provider=provider_name,
            start=start.isoformat(), end=end.isoformat(),
        )
        raw_bars = await provider.fetch_bars(instrument, "1m", start, end)
        if not raw_bars:
            return {
                "instrument": instrument,
                "provider": provider_name,
                "base_bars_fetched": 0,
                "timeframes": {},
                "warning": f"No data returned from {provider_name} for {instrument}",
            }

        all_bars = BarAggregator.build_all_timeframes(raw_bars)
        results: dict[str, dict[str, Any]] = {}
        for timeframe, timeframe_bars in all_bars.items():
            if timeframe_bars:
                results[timeframe] = await self.ingest_bars(timeframe_bars)
        return {
            "instrument": instrument,
            "provider": provider_name,
            "base_bars_fetched": len(raw_bars),
            "timeframes": results,
        }

    async def get_bar_count(self, instrument: str, timeframe: str) -> int:
        instrument_model = await self.get_instrument_by_symbol(instrument)
        if instrument_model is None:
            return 0
        result = await self.session.execute(
            text("SELECT COUNT(*) FROM bars WHERE instrument_id = :inst_id AND timeframe = :tf"),
            {"inst_id": instrument_model.id, "tf": timeframe},
        )
        return result.scalar() or 0

    async def query_bars(
        self,
        instrument: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        session: str | None = None,
        limit: int = 5000,
    ) -> list[Bar]:
        instrument_model = await self.get_instrument_by_symbol(instrument)
        if instrument_model is None:
            return []
        conditions = [Bar.instrument_id == instrument_model.id, Bar.timeframe == timeframe]
        if start:
            conditions.append(Bar.timestamp >= start)
        if end:
            conditions.append(Bar.timestamp <= end)
        if session:
            conditions.append(Bar.session == session)
        result = await self.session.execute(
            select(Bar).where(*conditions).order_by(Bar.timestamp.asc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_bar(self, instrument: str, timeframe: str) -> Bar | None:
        instrument_model = await self.get_instrument_by_symbol(instrument)
        if instrument_model is None:
            return None
        result = await self.session.execute(
            select(Bar)
            .where(Bar.instrument_id == instrument_model.id, Bar.timeframe == timeframe)
            .order_by(Bar.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def _timestamp_text(timestamp: Any) -> str | None:
    return timestamp.isoformat() if isinstance(timestamp, datetime) else None
