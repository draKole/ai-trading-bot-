"""Market Data Service — ingest, normalize, store, and retrieve OHLCV data.

Architecture:
    Provider (CSV, yfinance, Polygon, IBKR) → OHLCVBar (canonical)
    → Validator → BarAggregator → TimescaleDB (hypertable)

Key components:
    - DataProvider (ABC): abstract interface for data sources
    - OHLCVBar: canonical dataclass all providers normalize into
    - CSVProvider: import from CSV files
    - YFinanceProvider: Yahoo Finance historical data
    - BarAggregator: build higher-TF bars from lower-TF
    - BarValidator: deduplicate, detect gaps, validate OHLCV
    - MarketDataService: orchestrate ingestion, storage, retrieval
"""

from app.services.market_data.provider import (
    DataProvider,
    OHLCVBar,
    ProviderRegistry,
    VALID_TIMEFRAMES,
    TIMEFRAME_MINUTES,
    TIMEFRAME_REQUIRES,
)
from app.services.market_data.csv_provider import CSVProvider
from app.services.market_data.yfinance_provider import YFinanceProvider
from app.services.market_data.aggregator import BarAggregator
from app.services.market_data.validator import BarValidator, ValidationResult
from app.services.market_data.service import MarketDataService

# Register default providers
ProviderRegistry.register(CSVProvider())
ProviderRegistry.register(YFinanceProvider())

__all__ = [
    "DataProvider",
    "OHLCVBar",
    "ProviderRegistry",
    "VALID_TIMEFRAMES",
    "TIMEFRAME_MINUTES",
    "TIMEFRAME_REQUIRES",
    "CSVProvider",
    "YFinanceProvider",
    "BarAggregator",
    "BarValidator",
    "ValidationResult",
    "MarketDataService",
]
