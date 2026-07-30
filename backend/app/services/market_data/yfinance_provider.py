"""Yahoo Finance Data Provider — historical futures data via yfinance.

NOTE: yfinance support for CME futures is limited and varies by symbol.
- MNQ, NQ, MES, ES require "=F" suffix: "MNQ=F", "NQ=F", "MES=F", "ES=F"
- Data availability and quality varies — this provider should be verified
  against a known-good source before relying on it for production backtesting.
- yfinance is rate-limited and may return empty data for some periods.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import requests

from app.services.market_data.provider import DataProvider, OHLCVBar

# Eastern Time offset: UTC-5 (EST), UTC-4 (EDT) — use fixed for simplicity
ET_OFFSET = timedelta(hours=-5)

# RTH session: 9:30 AM – 4:00 PM ET
RTH_START_HOUR = 9
RTH_START_MIN = 30
RTH_END_HOUR = 16
RTH_END_MIN = 0


def _infer_session(ts: datetime) -> str:
    """Infer trading session from timestamp (UTC → ET).

    RTH = Regular Trading Hours (9:30-16:00 ET, Mon-Fri)
    ETH = Extended Trading Hours (outside RTH)
    """
    et = ts.astimezone(timezone(ET_OFFSET))
    # Weekday check: Monday=0, Sunday=6
    if et.weekday() >= 5:
        return "ETH"

    rth_start = et.replace(hour=RTH_START_HOUR, minute=RTH_START_MIN, second=0, microsecond=0)
    rth_end = et.replace(hour=RTH_END_HOUR, minute=RTH_END_MIN, second=0, microsecond=0)

    if rth_start <= et < rth_end:
        return "RTH"
    return "ETH"


def _compute_vwap(high: float, low: float, close: float, volume: int) -> float:
    """Approximate VWAP as typical price when true VWAP is unavailable.

    yfinance does not provide VWAP — we use (H + L + C) / 3 as a
    reasonable approximation for VWAP per bar.
    """
    if volume <= 0:
        return round((high + low + close) / 3.0, 6)
    return round((high + low + close) / 3.0, 6)


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
        days = (end - start).days

        if timeframe == "1m":
            if days <= 7:
                yf_interval = "1m"
            elif days <= 60:
                yf_interval = "5m"
            elif days <= 730:
                yf_interval = "60m"
            else:
                yf_interval = "1d"
        else:
            yf_interval = self._to_yf_interval(timeframe)

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}"

        params = {
            "interval": yf_interval,
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "includePrePost": "false",
            "events": "div,splits",
        }

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()

        data = response.json()["chart"]["result"][0]

        timestamps = data["timestamp"]
        quote = data["indicators"]["quote"][0]

        bars: list[OHLCVBar] = []

        for i, ts in enumerate(timestamps):
            if quote["open"][i] is None:
                continue

            o = float(quote["open"][i])
            h = float(quote["high"][i])
            l = float(quote["low"][i])
            c = float(quote["close"][i])
            v = int(quote["volume"][i] or 0)
            bar_ts = datetime.fromtimestamp(ts)

            bars.append(
                OHLCVBar(
                    instrument=instrument,
                    timeframe=timeframe,
                    timestamp=bar_ts,
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=v,
                    provider="yfinance",
                    vwap=_compute_vwap(h, l, c, v),
                    session=_infer_session(bar_ts),
                )
            )

        return bars

    async def is_available(self) -> bool:
        """yfinance is always available — no API key needed."""
        return True

