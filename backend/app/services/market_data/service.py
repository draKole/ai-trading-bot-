"""Market Data Service — orchestrate data ingestion, storage, and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, text

from app.services.market_data.provider import (
    DataProvider,
    OHLCVBar,
    VALID_TIMEFRAMES,
    ProviderRegistry,
)
from app.services.market_data.aggregator import BarAggregator
from app.services.market_data.validator import (
    BarValidator,
    ValidationResult,
    detect_overlapping_bars,
)
from app.models.instrument import Instrument, DEFAULT_INSTRUMENTS
from app.models.bar import Bar

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class MarketDataService:
    """Primary service for market data operations.

    Handles: provider management, data ingestion, normalization,
    aggregation, validation, and database storage/retrieval.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ─── Instrument Management ───────────────────────────────

    async def seed_instruments(self) -> list[Instrument]:
        """Ensure default instruments exist in the database."""
        existing = await self.list_instruments()
        existing_symbols = {i.symbol for i in existing}

        new_instruments: list[Instrument] = []
        for spec in DEFAULT_INSTRUMENTS:
            if spec["symbol"] not in existing_symbols:
                inst = Instrument(**spec)
                self.session.add(inst)
                new_instruments.append(inst)

        if new_instruments:
            await self.session.flush()
            logger.info("instruments_seeded", count=len(new_instruments))

        return new_instruments

    async def list_instruments(self) -> list[Instrument]:
        """List all active instruments."""
        result = await self.session.execute(
            select(Instrument).where(Instrument.is_active == True).order_by(Instrument.symbol)  # noqa: E712
        )
        return list(result.scalars().all())

    async def get_instrument_by_symbol(self, symbol: str) -> Instrument | None:
        """Look up an instrument by its symbol."""
        result = await self.session.execute(
            select(Instrument).where(Instrument.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()

    # ─── Data Ingestion ──────────────────────────────────────

    async def ingest_bars(
        self,
        bars: list[OHLCVBar],
    ) -> dict:
        """Validate, deduplicate, and store a batch of bars.

        Returns a summary dict with counts.
        """
        # 1. Validate and deduplicate within the batch
        validation = BarValidator.validate_and_deduplicate(bars)

        # 2. Check against existing bars in the database
        if validation.valid_bars:
            existing = await self._get_existing_bars_for_check(validation.valid_bars)
            new_bars = detect_overlapping_bars(
                [self._bar_to_ohclv(b) for b in existing],
                validation.valid_bars,
            )
        else:
            new_bars = []

        # 3. Resolve instrument IDs and insert
        instrument_cache: dict[str, int] = {}
        inserted = 0
        for bar in new_bars:
            if bar.instrument not in instrument_cache:
                inst = await self.get_instrument_by_symbol(bar.instrument)
                if inst is None:
                    logger.warning("unknown_instrument", instrument=bar.instrument)
                    continue
                instrument_cache[bar.instrument] = inst.id

            db_bar = Bar(
                instrument_id=instrument_cache[bar.instrument],
                timeframe=bar.timeframe,
                timestamp=bar.timestamp,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                provider=bar.provider,
                ingested_at=datetime.utcnow(),
            )
            self.session.add(db_bar)
            inserted += 1

        await self.session.flush()

        return {
            "submitted": len(bars),
            "valid": len(new_bars),
            "inserted": inserted,
            "duplicates_in_batch": len(validation.duplicates),
            "invalid": len(validation.invalid_bars),
            "duplicates_in_db": len(validation.valid_bars) - len(new_bars),
            "gaps_detected": len(validation.gaps),
            "gaps": validation.gaps[:10],
        }

    async def _get_existing_bars_for_check(
        self, bars: list[OHLCVBar],
    ) -> list[Bar]:
        """Query existing bars that overlap with the provided bar set."""
        if not bars:
            return []

        instrument = bars[0].instrument
        timeframe = bars[0].timeframe
        provider = bars[0].provider
        inst = await self.get_instrument_by_symbol(instrument)
        if inst is None:
            return []

        min_ts = min(b.timestamp for b in bars)
        max_ts = max(b.timestamp for b in bars)

        result = await self.session.execute(
            select(Bar).where(
                Bar.instrument_id == inst.id,
                Bar.timeframe == timeframe,
                Bar.provider == provider,
                Bar.timestamp >= min_ts,
                Bar.timestamp <= max_ts,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    def _bar_to_ohclv(db_bar: Bar) -> OHLCVBar:
        """Convert a database Bar to a canonical OHLCVBar."""
        return OHLCVBar(
            instrument="",  # Not available from Bar alone
            timeframe=db_bar.timeframe,
            timestamp=db_bar.timestamp,
            open=db_bar.open,
            high=db_bar.high,
            low=db_bar.low,
            close=db_bar.close,
            volume=db_bar.volume,
            provider=db_bar.provider,
        )

    # ─── Data Retrieval ──────────────────────────────────────

    async def get_bars(
        self,
        instrument: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 5000,
    ) -> list[Bar]:
        """Retrieve stored bars for an instrument/timeframe."""
        inst = await self.get_instrument_by_symbol(instrument)
        if inst is None:
            return []

        conditions = [
            Bar.instrument_id == inst.id,
            Bar.timeframe == timeframe,
        ]
        if start:
            conditions.append(Bar.timestamp >= start)
        if end:
            conditions.append(Bar.timestamp <= end)

        result = await self.session.execute(
            select(Bar)
            .where(*conditions)
            .order_by(Bar.timestamp.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_available_timeframes(
        self, instrument: str,
    ) -> list[str]:
        """Return timeframes that have data for a given instrument."""
        inst = await self.get_instrument_by_symbol(instrument)
        if inst is None:
            return []

        result = await self.session.execute(
            select(Bar.timeframe)
            .where(Bar.instrument_id == inst.id)
            .distinct()
            .order_by(Bar.timeframe)
        )
        return [row[0] for row in result.all()]

    # ─── Full Ingestion Pipeline ─────────────────────────────

    async def fetch_and_ingest(
        self,
        instrument: str,
        start: datetime,
        end: datetime,
        provider_name: str = "yfinance",
    ) -> dict:
        """Full pipeline: fetch 1m bars → aggregate all TFs → validate → store.

        Returns a summary per timeframe.
        """
        provider = ProviderRegistry.get(provider_name)
        if provider is None:
            raise ValueError(f"Unknown provider: {provider_name}")

        # Ensure instruments exist
        await self.seed_instruments()

        # Fetch base timeframe (1m)
        logger.info(
            "fetching_data",
            instrument=instrument,
            provider=provider_name,
            start=start.isoformat(),
            end=end.isoformat(),
        )
        raw_bars = await provider.fetch_bars(instrument, "1m", start, end)

        if not raw_bars:
            return {"error": f"No data returned from {provider_name} for {instrument}"}

        # Aggregate to all timeframes
        all_bars = BarAggregator.build_all_timeframes(raw_bars)

        # Ingest each timeframe
        results: dict[str, dict] = {}
        for tf, bars in all_bars.items():
            if bars:
                results[tf] = await self.ingest_bars(bars)

        return {
            "instrument": instrument,
            "provider": provider_name,
            "base_bars_fetched": len(raw_bars),
            "timeframes": results,
        }

    async def get_bar_count(
        self, instrument: str, timeframe: str,
    ) -> int:
        """Count bars for an instrument/timeframe."""
        inst = await self.get_instrument_by_symbol(instrument)
        if inst is None:
            return 0

        result = await self.session.execute(
            text(
                "SELECT COUNT(*) FROM bars "
                "WHERE instrument_id = :inst_id AND timeframe = :tf"
            ),
            {"inst_id": inst.id, "tf": timeframe},
        )
        return result.scalar() or 0
