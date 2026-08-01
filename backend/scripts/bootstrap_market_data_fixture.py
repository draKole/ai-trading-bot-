"""Seed deterministic market-data rows for the isolated CI runtime proof.

This module is intentionally opt-in. It must never be enabled in a deployment:
the fixture represents provider capability and recent stored data, not external
market availability. Production environments remain dependent on real imports.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.bar import Bar
from app.models.instrument import Instrument

SYMBOLS = ("ES", "MES", "NQ", "MNQ")


async def bootstrap() -> int:
    """Insert one valid recent bar per required instrument, idempotently."""
    if os.getenv("MARKET_DATA_BOOTSTRAP_CI", "false").lower() != "true":
        return 0
    timestamp = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=1)
    inserted = 0
    async with async_session_factory() as session:
        rows = await session.execute(select(Instrument).where(Instrument.symbol.in_(SYMBOLS)))
        instruments = {instrument.symbol: instrument for instrument in rows.scalars()}
        missing = [symbol for symbol in SYMBOLS if symbol not in instruments]
        if missing:
            raise RuntimeError(f"Required instruments missing after migrations: {missing}")
        for symbol in SYMBOLS:
            instrument = instruments[symbol]
            exists = await session.scalar(
                select(Bar.id).where(
                    Bar.instrument_id == instrument.id,
                    Bar.timeframe == "1m",
                    Bar.timestamp == timestamp,
                    Bar.provider == "ci-fixture",
                )
            )
            if exists is not None:
                continue
            # Synthetic values are deliberately marked ci-fixture and are only
            # used to prove persistence/probe wiring in a clean CI database.
            base = {"ES": 5000.0, "MES": 500.0, "NQ": 18000.0, "MNQ": 1800.0}[symbol]
            session.add(Bar(
                instrument_id=instrument.id, timeframe="1m", timestamp=timestamp,
                open=base, high=base + 1.0, low=base - 1.0, close=base + 0.5,
                volume=1, vwap=base + 0.25, session="RTH", provider="ci-fixture",
            ))
            inserted += 1
        await session.commit()
    return inserted


if __name__ == "__main__":
    print(f"[market-data-fixture] inserted {asyncio.run(bootstrap())} CI bars")
