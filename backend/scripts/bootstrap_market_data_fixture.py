"""Seed deterministic market-data rows for the isolated CI runtime proof.

This module is intentionally opt-in. It must never be enabled in a deployment:
the fixture represents provider capability and recent stored data, not external
market availability. Production environments remain dependent on real imports.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.database import async_session_factory

SYMBOLS = ("ES", "MES", "NQ", "MNQ")


async def bootstrap() -> int:
    """Insert one valid recent bar per required instrument, idempotently.

    Uses SQL against the already-migrated schema so this CI-only hook cannot
    depend on ORM metadata or application startup imports.
    """
    if os.getenv("MARKET_DATA_BOOTSTRAP_CI", "false").lower() != "true":
        return 0
    timestamp = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=1)
    bases = {"ES": 5000.0, "MES": 500.0, "NQ": 18000.0, "MNQ": 1800.0}
    inserted = 0
    async with async_session_factory() as session:
        rows = (await session.execute(
            text("SELECT symbol, id FROM instruments WHERE symbol = ANY(:symbols)"),
            {"symbols": list(SYMBOLS)},
        )).all()
        instruments = {symbol: instrument_id for symbol, instrument_id in rows}
        missing = [symbol for symbol in SYMBOLS if symbol not in instruments]
        if missing:
            raise RuntimeError(f"Required instruments missing after migrations: {missing}")
        for symbol, base in bases.items():
            result = await session.execute(text("""
                INSERT INTO bars
                    (instrument_id, timeframe, timestamp, open, high, low, close,
                     volume, vwap, session, provider)
                VALUES
                    (:instrument_id, '1m', :timestamp, :open, :high, :low, :close,
                     1, :vwap, 'RTH', 'ci-fixture')
                ON CONFLICT (instrument_id, timeframe, timestamp, provider) DO NOTHING
            """), {"instrument_id": instruments[symbol], "timestamp": timestamp,
                    "open": base, "high": base + 1.0, "low": base - 1.0,
                    "close": base + 0.5, "vwap": base + 0.25})
            inserted += result.rowcount
        await session.commit()
    return inserted


if __name__ == "__main__":
    print(f"[market-data-fixture] inserted {asyncio.run(bootstrap())} CI bars")
