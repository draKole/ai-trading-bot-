"""Market Data Service — ingest, normalize, and store OHLCV data.

Architecture:
    Multiple data sources (yfinance, Polygon, IBKR, CSV) → normalizer → TimescaleDB.
    All downstream engines consume normalized bars — they never know the source.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OHLCVBar:
    """Normalized OHLCV bar — the universal data type."""
    instrument: str
    timeframe: str          # "1m", "3m", "5m", "15m", "1h", "4h", "1d"
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    provider: str           # "yfinance", "polygon", "ibkr", "csv"


class DataProvider(ABC):
    """Abstract interface for market data providers."""

    @abstractmethod
    async def fetch_bars(
        self, instrument: str, timeframe: str,
        start: datetime, end: datetime,
    ) -> list[OHLCVBar]:
        """Fetch historical OHLCV bars."""
        ...

    @abstractmethod
    async def stream_bars(
        self, instrument: str, timeframe: str,
    ) -> None:
        """Subscribe to real-time bar stream."""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check provider connection status."""
        ...


class BarAggregator:
    """Builds higher-timeframe bars from lower-timeframe bars.

    Example: 1m bars → 5m, 15m, 1h, etc.
    Not yet implemented — interface defined for Phase 1.
    """
    pass
