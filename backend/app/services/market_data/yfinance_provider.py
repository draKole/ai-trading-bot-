"""Yahoo Finance provider for bounded historical futures imports.

Yahoo's chart endpoint is useful for development data but it is not a
production market-data feed.  In particular, its one-minute history is limited
to a short rolling window.  This provider refuses to silently substitute a
coarser interval because doing so would corrupt the stored timeframe label.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from app.services.market_data.provider import DataProvider, OHLCVBar

ET = ZoneInfo("America/New_York")
# Retained for compatibility with existing callers/tests.  Session inference
# itself uses America/New_York so daylight-saving transitions are correct.
ET_OFFSET = timedelta(hours=-5)
RTH_START_HOUR = 9
RTH_START_MIN = 30
RTH_END_HOUR = 16
RTH_END_MIN = 0
YFINANCE_REQUEST_TIMEOUT_SECONDS = 30
YFINANCE_MAX_1M_RANGE = timedelta(days=7)


def _infer_session(ts: datetime) -> str:
    """Infer RTH/ETH from a UTC timestamp using the New York timezone."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    et = ts.astimezone(ET)
    if et.weekday() >= 5:
        return "ETH"
    rth_start = et.replace(hour=RTH_START_HOUR, minute=RTH_START_MIN, second=0, microsecond=0)
    rth_end = et.replace(hour=RTH_END_HOUR, minute=RTH_END_MIN, second=0, microsecond=0)
    return "RTH" if rth_start <= et < rth_end else "ETH"


def _compute_vwap(high: float, low: float, close: float, volume: int) -> float:
    """Approximate a per-bar VWAP with typical price when unavailable."""
    return round((high + low + close) / 3.0, 6)


class YFinanceProvider(DataProvider):
    """Fetch historical OHLCV bars from Yahoo Finance's chart endpoint."""

    name = "yfinance"
    SYMBOL_MAP: dict[str, str] = {
        "MNQ": "MNQ=F", "NQ": "NQ=F", "MES": "MES=F", "ES": "ES=F",
    }
    INTERVAL_MAP: dict[str, str] = {
        "1m": "1m", "5m": "5m", "15m": "15m", "1h": "60m", "1d": "1d",
    }
    UNSUPPORTED_TIMEFRAMES: set[str] = {"3m", "4h"}

    def _to_yf_symbol(self, instrument: str) -> str:
        return self.SYMBOL_MAP.get(instrument.upper(), instrument.upper())

    def _to_yf_interval(self, timeframe: str) -> str:
        if timeframe in self.UNSUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"yfinance does not support timeframe '{timeframe}'. "
                "Use bar aggregation from a lower timeframe instead."
            )
        if timeframe not in self.INTERVAL_MAP:
            raise ValueError(f"yfinance does not support timeframe '{timeframe}'")
        return self.INTERVAL_MAP[timeframe]

    async def fetch_bars(
        self,
        instrument: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]:
        """Fetch a single, accurately-labelled timeframe.

        The asynchronous HTTP request has an explicit timeout so an upstream
        outage cannot block the FastAPI event loop.
        """
        if end <= start:
            raise ValueError("end must be later than start")
        if timeframe == "1m" and end - start > YFINANCE_MAX_1M_RANGE:
            raise ValueError(
                "yfinance 1m imports are limited to 7 days; split the range "
                "into 7-day requests rather than storing coarser bars as 1m"
            )

        yf_symbol = self._to_yf_symbol(instrument)
        yf_interval = self._to_yf_interval(timeframe)
        params = {
            "interval": yf_interval,
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "includePrePost": "false",
            "events": "div,splits",
        }
        try:
            async with httpx.AsyncClient(timeout=YFINANCE_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}",
                    params=params,
                    headers={"User-Agent": "DrakeAITrading/1.0"},
                )
            response.raise_for_status()
            payload = response.json()
            chart = payload.get("chart", {})
            if chart.get("error"):
                raise ValueError(f"yfinance returned an error: {chart['error']}")
            data = (chart.get("result") or [None])[0]
            if not data:
                return []
            timestamps = data.get("timestamp") or []
            quote = ((data.get("indicators") or {}).get("quote") or [{}])[0]
        except httpx.HTTPError as exc:
            raise ValueError(f"yfinance request failed: {exc}") from exc
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("yfinance"):
                raise
            raise ValueError(f"invalid yfinance response: {exc}") from exc

        bars: list[OHLCVBar] = []
        for index, epoch_seconds in enumerate(timestamps):
            try:
                open_price = quote.get("open", [])[index]
                high = quote.get("high", [])[index]
                low = quote.get("low", [])[index]
                close = quote.get("close", [])[index]
                if None in (open_price, high, low, close):
                    continue
                volume = int((quote.get("volume", [])[index] or 0))
                timestamp = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
                bars.append(OHLCVBar(
                    instrument=instrument.upper(),
                    timeframe=timeframe,
                    timestamp=timestamp,
                    open=float(open_price),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=volume,
                    provider=self.name,
                    vwap=_compute_vwap(float(high), float(low), float(close), volume),
                    session=_infer_session(timestamp),
                ))
            except (IndexError, TypeError, ValueError, OSError):
                # Sparse or malformed points are skipped; the validation summary
                # on the resulting import exposes any genuine time gaps.
                continue
        return bars

    async def is_available(self) -> bool:
        """The provider needs no credentials; requests are checked at fetch time."""
        return True
