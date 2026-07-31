"""Focused regression tests for reliable historical-data imports."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.services.market_data.aggregator import BarAggregator
from app.services.market_data.csv_provider import CSVProvider
from app.services.market_data.provider import OHLCVBar
from app.services.market_data.validator import BarValidator
from app.services.market_data.yfinance_provider import YFinanceProvider


def _bar(instrument: str, timestamp: datetime, *, vwap: float = 100.0, volume: int = 10) -> OHLCVBar:
    return OHLCVBar(
        instrument=instrument,
        timeframe="1m",
        timestamp=timestamp,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=volume,
        provider="test",
        vwap=vwap,
        session="RTH",
    )


class TestCanonicalImportParsing:
    def test_from_dict_normalizes_symbol_and_naive_timestamp_to_utc(self):
        bar = OHLCVBar.from_dict({
            "instrument": " es ", "timeframe": "1m", "timestamp": "2026-01-15T10:00:00",
            "open": "100", "high": "102", "low": "99", "close": "101", "volume": "25",
        })
        assert bar.instrument == "ES"
        assert bar.timestamp.tzinfo == timezone.utc
        assert bar.provider == "import"
        assert bar.is_valid()

    def test_from_dict_rejects_missing_and_non_finite_values(self):
        with pytest.raises(ValueError, match="missing required"):
            OHLCVBar.from_dict({"instrument": "ES"})
        bar = OHLCVBar.from_dict({
            "instrument": "ES", "timeframe": "1m", "timestamp": "2026-01-15T10:00:00Z",
            "open": "nan", "high": 102, "low": 99, "close": 101, "volume": 1,
        })
        assert "open must be finite" in bar.validate()

    def test_validator_keeps_series_separate_when_detecting_gaps(self):
        base = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
        # These timestamps are far apart globally, but each individual series
        # is complete. Mixed imports must not report a fabricated gap.
        result = BarValidator.validate_and_deduplicate([
            _bar("ES", base),
            _bar("NQ", base + timedelta(minutes=10)),
            _bar("NQ", base + timedelta(minutes=11)),
        ])
        assert result.gaps == []


class TestCSVImportReporting:
    def test_csv_returns_valid_bars_and_row_level_errors(self, tmp_path):
        csv_file = tmp_path / "bars.csv"
        csv_file.write_text(
            "\ufefftimestamp,open,high,low,close,volume\n"
            "2026-01-15T10:00:00Z,100,102,99,101,10\n"
            "2026-01-15T10:01:00Z,100,98,99,101,10\n",
            encoding="utf-8",
        )
        parsed = CSVProvider(default_instrument="ES", default_timeframe="1m").load_file_with_report(csv_file)
        assert len(parsed.bars) == 1
        assert parsed.bars[0].timestamp.tzinfo == timezone.utc
        assert len(parsed.errors) == 1
        assert parsed.errors[0]["row"] == 3


class TestAggregationMetadata:
    def test_aggregate_preserves_volume_weighted_vwap_and_session(self):
        base = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
        aggregated = BarAggregator.aggregate([
            _bar("ES", base, vwap=100.0, volume=10),
            _bar("ES", base + timedelta(minutes=1), vwap=110.0, volume=30),
        ], "3m")
        assert len(aggregated) == 1
        assert aggregated[0].vwap == 107.5
        assert aggregated[0].session == "RTH"


class TestYFinanceImportBounds:
    def test_one_minute_fetch_refuses_to_mislabel_coarser_history(self):
        provider = YFinanceProvider()
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="limited to 7 days"):
            asyncio.run(provider.fetch_bars("ES", "1m", start, start + timedelta(days=8)))

    def test_yfinance_bars_have_utc_timestamps(self, monkeypatch):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "chart": {
                        "result": [{
                            "timestamp": [1768471200],
                            "indicators": {"quote": [{
                                "open": [100.0], "high": [102.0], "low": [99.0],
                                "close": [101.0], "volume": [10],
                            }]},
                        }],
                    },
                }

        class AsyncClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return None

            async def get(self, *args, **kwargs):
                return Response()

        monkeypatch.setattr("app.services.market_data.yfinance_provider.httpx.AsyncClient", AsyncClient)
        start = datetime(2026, 1, 15, tzinfo=timezone.utc)
        bars = asyncio.run(YFinanceProvider().fetch_bars("ES", "1m", start, start + timedelta(days=1)))
        assert len(bars) == 1
        assert bars[0].timestamp.tzinfo == timezone.utc
        assert bars[0].instrument == "ES"
