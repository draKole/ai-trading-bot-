"""Yahoo Finance Data Provider — historical futures data via yfinance.

NOTE: yfinance support for CME futures is limited and varies by symbol.
- MNQ, NQ, MES, ES require "=F" suffix: "MNQ=F", "NQ=F", "MES=F", "ES=F"
- Data availability and quality varies — this provider should be verified
  against a known-good source before relying on it for production backtesting.
- yfinance is rate-limited and may return empty data for some periods.
"""

from __future__ import annotations

from datetime import datetime

import yfinance as yf

from app.services.market_data.provider import DataProvider, OHLCVBar


class YFinanceProvider(DataProvider):
    """Fetch historical OHLCV bars from Yahoo Finance."""

    name = "yfinance"

    # yfinance symbol mapping for CME futures
    SYMBOL_MAP: dict[str, str] = {
        "MNQ": "MNQ=F",
        "NQ": "NQ=F",
        "MES": "MES=F",
        "ES": "ES=F",
    }

    # yfinance interval mapping
    INTERVAL_MAP: dict[str, str] = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "60m",
        "1d": "1d",
    }

    # yfinance does NOT support 3m or 4h natively
    UNSUPPORTED_TIMEFRAMES: set[str] = {"3m", "4h"}

    def _to_yf_symbol(self, instrument: str) -> str:
        return self.SYMBOL_MAP.get(instrument, instrument)

    def _to_yf_interval(self, timeframe: str) -> str:
        if timeframe in self.UNSUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"yfinance does not support timeframe '{timeframe}'. "
                f"Use bar aggregation from a lower timeframe instead."
            )
        return self.INTERVAL_MAP.get(timeframe, timeframe)

    async def fetch_bars(
        self,
        instrument: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]:
        """Fetch historical bars from Yahoo Finance."""
        yf_symbol = self._to_yf_symbol(instrument)
        yf_interval = self._to_yf_interval(timeframe)

        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(
            interval=yf_interval,
            start=start,
            end=end,
            auto_adjust=False,
        )

        if df.empty:
            return []

        bars: list[OHLCVBar] = []
        for ts, row in df.iterrows():
            bar = OHLCVBar(
                instrument=instrument,
                timeframe=timeframe,
                timestamp=ts.to_pydatetime(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
                provider="yfinance",
            )
            if bar.is_valid():
                bars.append(bar)

        return bars

    async def is_available(self) -> bool:
        """yfinance is always available — no API key needed."""
        return True
