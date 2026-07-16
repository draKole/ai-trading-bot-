"""Data Provider abstraction and registry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ─── Canonical Data Model ────────────────────────────────────

@dataclass
class OHLCVBar:
    """Canonical OHLCV bar — all providers normalize into this."""
    instrument: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    provider: str

    def validate(self) -> list[str]:
        """Return list of validation error messages. Empty = valid."""
        errors = []
        if not self.instrument:
            errors.append("instrument is empty")
        if not self.timeframe:
            errors.append("timeframe is empty")
        if self.timestamp is None:
            errors.append("timestamp is None")
        if self.high < self.low:
            errors.append(f"high ({self.high}) < low ({self.low})")
        if self.open < self.low or self.open > self.high:
            errors.append(f"open ({self.open}) outside [{self.low}, {self.high}]")
        if self.close < self.low or self.close > self.high:
            errors.append(f"close ({self.close}) outside [{self.low}, {self.high}]")
        if self.volume < 0:
            errors.append(f"negative volume: {self.volume}")
        return errors

    def is_valid(self) -> bool:
        return len(self.validate()) == 0


# ─── Valid Timeframes ────────────────────────────────────────

VALID_TIMEFRAMES = ["1m", "3m", "5m", "15m", "1h", "4h", "1d"]

# Timeframe to minutes mapping for aggregation
TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440,
}

# Timeframe dependency: higher TF can be built from which lower TF
TIMEFRAME_REQUIRES: dict[str, str] = {
    "3m": "1m",
    "5m": "1m",
    "15m": "5m",
    "1h": "15m",
    "4h": "1h",
    "1d": "1h",
}


# ─── Provider Interface ──────────────────────────────────────

class DataProvider(ABC):
    """Abstract base for all market data providers.

    Each provider fetches data from its source and returns
    a list of canonical OHLCVBar objects.
    """

    name: str = "base"

    @abstractmethod
    async def fetch_bars(
        self,
        instrument: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]:
        """Fetch historical OHLCV bars for an instrument and timeframe."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available/configured."""
        ...


# ─── Provider Registry ───────────────────────────────────────

class ProviderRegistry:
    """Registry of available data providers."""

    _providers: dict[str, DataProvider] = {}

    @classmethod
    def register(cls, provider: DataProvider) -> None:
        cls._providers[provider.name] = provider

    @classmethod
    def get(cls, name: str) -> DataProvider | None:
        return cls._providers.get(name)

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._providers.keys())

    @classmethod
    def clear(cls) -> None:
        cls._providers.clear()
