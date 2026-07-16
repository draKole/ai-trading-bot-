"""Phase 1A Tests — Market Data Foundation.

Tests cover: OHLCVBar validation, CSV provider, bar aggregation,
duplicate detection, gap detection, and API endpoints.
"""

from datetime import datetime, timedelta
import tempfile
import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.market_data.provider import (
    OHLCVBar,
    VALID_TIMEFRAMES,
    TIMEFRAME_MINUTES,
    TIMEFRAME_REQUIRES,
    ProviderRegistry,
)
from app.services.market_data.csv_provider import CSVProvider
from app.services.market_data.aggregator import BarAggregator
from app.services.market_data.validator import (
    BarValidator,
    ValidationResult,
    detect_overlapping_bars,
)


# ─── OHLCVBar Model Tests ────────────────────────────────────

class TestOHLCVBar:
    """Tests for the canonical OHLCVBar model."""

    def test_valid_bar_passes_validation(self):
        bar = OHLCVBar(
            instrument="MNQ", timeframe="1m",
            timestamp=datetime(2025, 1, 15, 10, 0),
            open=21000.0, high=21010.0, low=20990.0, close=21005.0,
            volume=100, provider="test",
        )
        assert bar.is_valid()
        assert bar.validate() == []

    def test_high_less_than_low_fails(self):
        bar = OHLCVBar(
            instrument="MNQ", timeframe="1m",
            timestamp=datetime(2025, 1, 15, 10, 0),
            open=21000.0, high=20990.0, low=21010.0, close=21005.0,
            volume=100, provider="test",
        )
        assert not bar.is_valid()
        assert any("high" in e for e in bar.validate())

    def test_open_outside_range_fails(self):
        bar = OHLCVBar(
            instrument="MNQ", timeframe="1m",
            timestamp=datetime(2025, 1, 15, 10, 0),
            open=22000.0, high=21010.0, low=20990.0, close=21005.0,
            volume=100, provider="test",
        )
        assert not bar.is_valid()

    def test_close_outside_range_fails(self):
        bar = OHLCVBar(
            instrument="MNQ", timeframe="1m",
            timestamp=datetime(2025, 1, 15, 10, 0),
            open=21000.0, high=21010.0, low=20990.0, close=19000.0,
            volume=100, provider="test",
        )
        assert not bar.is_valid()

    def test_negative_volume_fails(self):
        bar = OHLCVBar(
            instrument="MNQ", timeframe="1m",
            timestamp=datetime(2025, 1, 15, 10, 0),
            open=21000.0, high=21010.0, low=20990.0, close=21005.0,
            volume=-5, provider="test",
        )
        assert not bar.is_valid()

    def test_empty_instrument_fails(self):
        bar = OHLCVBar(
            instrument="", timeframe="1m",
            timestamp=datetime(2025, 1, 15, 10, 0),
            open=21000.0, high=21010.0, low=20990.0, close=21005.0,
            volume=100, provider="test",
        )
        assert not bar.is_valid()

    def test_none_timestamp_fails(self):
        bar = OHLCVBar(
            instrument="MNQ", timeframe="1m",
            timestamp=None,  # type: ignore
            open=21000.0, high=21010.0, low=20990.0, close=21005.0,
            volume=100, provider="test",
        )
        assert not bar.is_valid()

    def test_equal_high_low_open_close_is_valid(self):
        """Flat bar (no movement) should be valid."""
        bar = OHLCVBar(
            instrument="MNQ", timeframe="1m",
            timestamp=datetime(2025, 1, 15, 10, 0),
            open=21000.0, high=21000.0, low=21000.0, close=21000.0,
            volume=0, provider="test",
        )
        assert bar.is_valid()


# ─── CSV Provider Tests ──────────────────────────────────────

class TestCSVProvider:
    """Tests for CSV file import."""

    def test_load_valid_csv(self):
        csv_content = (
            "timestamp,open,high,low,close,volume\n"
            "2025-01-15T10:00:00,21000.0,21010.0,20990.0,21005.0,100\n"
            "2025-01-15T10:01:00,21005.0,21015.0,21000.0,21010.0,150\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False,
        ) as f:
            f.write(csv_content)
            path = f.name

        try:
            provider = CSVProvider(default_instrument="MNQ", default_timeframe="1m")
            bars = provider.load_file(path)
            assert len(bars) == 2
            assert bars[0].open == 21000.0
            assert bars[1].close == 21010.0
        finally:
            os.unlink(path)

    def test_csv_with_instrument_and_timeframe_columns(self):
        csv_content = (
            "timestamp,open,high,low,close,volume,instrument,timeframe\n"
            "2025-01-15T10:00:00,21000,21010,20990,21005,100,MNQ,1m\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False,
        ) as f:
            f.write(csv_content)
            path = f.name

        try:
            provider = CSVProvider(default_instrument="ES", default_timeframe="5m")
            bars = provider.load_file(path)
            assert len(bars) == 1
            # CSV column overrides default
            assert bars[0].instrument == "MNQ"
            assert bars[0].timeframe == "1m"
        finally:
            os.unlink(path)

    def test_missing_columns_raises_error(self):
        csv_content = "timestamp,open,close\n2025-01-15,21000,21005\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False,
        ) as f:
            f.write(csv_content)
            path = f.name

        try:
            provider = CSVProvider()
            with pytest.raises(ValueError, match="missing required columns"):
                provider.load_file(path)
        finally:
            os.unlink(path)

    def test_invalid_row_logged_but_rest_loaded(self):
        csv_content = (
            "timestamp,open,high,low,close,volume\n"
            "2025-01-15T10:00:00,21000,21010,20990,21005,100\n"
            "invalid,not,numbers,here,now,what\n"
            "2025-01-15T10:02:00,21010,21020,21005,21015,200\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False,
        ) as f:
            f.write(csv_content)
            path = f.name

        try:
            provider = CSVProvider(default_instrument="MNQ", default_timeframe="1m")
            bars = provider.load_file(path)
            # 2 valid bars, 1 invalid row skipped
            assert len(bars) == 2
        finally:
            os.unlink(path)


# ─── Bar Aggregator Tests ────────────────────────────────────

class TestBarAggregator:
    """Tests for building higher-TF bars from lower-TF bars."""

    @pytest.fixture
    def one_minute_bars(self):
        """Generate 10 minutes of 1m bars for MNQ."""
        base = datetime(2025, 1, 15, 10, 0)
        prices = [
            (100.0, 102.0, 99.0, 101.0, 50),
            (101.0, 103.0, 100.5, 102.5, 60),
            (102.5, 104.0, 102.0, 103.0, 40),
            (103.0, 103.5, 101.0, 101.5, 70),
            (101.5, 102.0, 100.0, 100.5, 55),
            (100.5, 101.5, 100.0, 101.0, 45),
            (101.0, 103.0, 100.5, 102.5, 65),
            (102.5, 104.0, 102.0, 103.5, 50),
            (103.5, 105.0, 103.0, 104.0, 80),
            (104.0, 106.0, 103.5, 105.0, 90),
        ]
        bars = []
        for i, (o, h, l, c, v) in enumerate(prices):
            bars.append(OHLCVBar(
                instrument="MNQ", timeframe="1m",
                timestamp=base + timedelta(minutes=i),
                open=o, high=h, low=l, close=c,
                volume=v, provider="test",
            ))
        return bars

    def test_1m_to_5m_aggregation(self, one_minute_bars):
        """Aggregate 10 1m bars into 2 5m bars."""
        result = BarAggregator.aggregate(one_minute_bars, "5m")
        assert len(result) == 2

        # First 5m bar: minutes 0-4
        assert result[0].open == 100.0     # first open
        assert result[0].high == 104.0     # max high
        assert result[0].low == 99.0       # min low
        assert result[0].close == 100.5    # last close
        assert result[0].volume == 275     # sum of 5 volumes

        # Second 5m bar: minutes 5-9
        assert result[1].open == 100.5
        assert result[1].high == 106.0
        assert result[1].low == 100.0
        assert result[1].close == 105.0
        assert result[1].volume == 330

    def test_1m_to_15m_aggregation(self, one_minute_bars):
        """10 1m bars → 1 partial 15m bar (only 10 of 15 minutes)."""
        result = BarAggregator.aggregate(one_minute_bars, "15m")
        assert len(result) == 1
        assert result[0].open == 100.0
        assert result[0].close == 105.0

    def test_cannot_aggregate_same_timeframe(self, one_minute_bars):
        with pytest.raises(ValueError, match="must be greater"):
            BarAggregator.aggregate(one_minute_bars, "1m")

    def test_cannot_aggregate_lower_timeframe(self, one_minute_bars):
        with pytest.raises(ValueError, match="must be greater"):
            BarAggregator.aggregate(one_minute_bars, "1m")

    def test_aggregate_empty_bars(self):
        result = BarAggregator.aggregate([], "5m")
        assert result == []

    def test_invalid_timeframe_raises(self, one_minute_bars):
        with pytest.raises(ValueError, match="Invalid timeframe"):
            BarAggregator.aggregate(one_minute_bars, "2m")

    def test_1m_to_daily_aggregation(self, one_minute_bars):
        result = BarAggregator.aggregate(one_minute_bars, "1d")
        assert len(result) == 1
        assert result[0].open == 100.0
        assert result[0].close == 105.0
        assert result[0].high == 106.0
        assert result[0].low == 99.0
        assert result[0].volume == 605

    def test_mtf_build_all_timeframes(self, one_minute_bars):
        """build_all_timeframes generates all higher TFs from 1m base."""
        all_tfs = BarAggregator.build_all_timeframes(one_minute_bars)
        assert "1m" in all_tfs
        assert "5m" in all_tfs
        assert "15m" in all_tfs
        assert "1h" in all_tfs
        assert "1d" in all_tfs
        assert len(all_tfs["1m"]) == 10
        assert len(all_tfs["5m"]) == 2

    def test_3m_aggregation(self, one_minute_bars):
        """4 3m bars from 10 1m bars (3 full buckets + 1 partial)."""
        result = BarAggregator.aggregate(one_minute_bars, "3m")
        assert len(result) == 4  # buckets: [0-2], [3-5], [6-8], [9]
        assert result[0].open == 100.0
        assert result[-1].close == 105.0


# ─── Validator Tests ─────────────────────────────────────────

class TestBarValidator:
    """Tests for validation, deduplication, and gap detection."""

    def test_no_issues_clean_batch(self):
        bars = [
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 0),
                     100, 102, 99, 101, 50, "test"),
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 1),
                     101, 103, 100, 102, 60, "test"),
        ]
        result = BarValidator.validate_and_deduplicate(bars)
        assert result.is_clean
        assert len(result.valid_bars) == 2
        assert result.total_rejected == 0

    def test_duplicates_removed(self):
        base_ts = datetime(2025, 1, 15, 10, 0)
        bars = [
            OHLCVBar("MNQ", "1m", base_ts, 100, 102, 99, 101, 50, "test"),
            OHLCVBar("MNQ", "1m", base_ts, 100, 102, 99, 101, 50, "test"),  # dup
            OHLCVBar("MNQ", "1m", base_ts + timedelta(minutes=1),
                     101, 103, 100, 102, 60, "test"),
        ]
        result = BarValidator.validate_and_deduplicate(bars)
        assert len(result.valid_bars) == 2
        assert len(result.duplicates) == 1

    def test_invalid_bars_removed(self):
        bars = [
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 0),
                     100, 102, 99, 101, 50, "test"),
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 1),
                     100, 90, 110, 101, 50, "test"),  # high < low
        ]
        result = BarValidator.validate_and_deduplicate(bars)
        assert len(result.valid_bars) == 1
        assert len(result.invalid_bars) == 1

    def test_gap_detection(self):
        """Two bars with a 5-minute gap should be detected."""
        bars = [
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 0),
                     100, 102, 99, 101, 50, "test"),
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 5),
                     101, 103, 100, 102, 60, "test"),  # 4 bars missing
        ]
        result = BarValidator.validate_and_deduplicate(bars)
        assert len(result.gaps) == 1
        assert result.gaps[0]["missing_bars"] == 4

    def test_no_gap_for_consecutive_bars(self):
        bars = [
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 0),
                     100, 102, 99, 101, 50, "test"),
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 1),
                     101, 103, 100, 102, 60, "test"),
        ]
        result = BarValidator.validate_and_deduplicate(bars)
        assert len(result.gaps) == 0

    def test_empty_list(self):
        result = BarValidator.validate_and_deduplicate([])
        assert result.is_clean
        assert len(result.valid_bars) == 0


# ─── Overlap Detection Tests ─────────────────────────────────

class TestOverlapDetection:
    """Tests for detecting overlapping bars between existing and new data."""

    def test_all_new_bars_passed_through(self):
        existing = [
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 0),
                     100, 102, 99, 101, 50, "test"),
        ]
        new = [
            OHLCVBar("MNQ", "1m", datetime(2025, 1, 15, 10, 1),
                     101, 103, 100, 102, 60, "test"),
        ]
        result = detect_overlapping_bars(existing, new)
        assert len(result) == 1

    def test_overlapping_bars_filtered(self):
        ts = datetime(2025, 1, 15, 10, 0)
        existing = [
            OHLCVBar("MNQ", "1m", ts, 100, 102, 99, 101, 50, "test"),
        ]
        new = [
            OHLCVBar("MNQ", "1m", ts, 100, 102, 99, 101, 50, "test"),  # overlap
            OHLCVBar("MNQ", "1m", ts + timedelta(minutes=1),
                     101, 103, 100, 102, 60, "test"),
        ]
        result = detect_overlapping_bars(existing, new)
        assert len(result) == 1  # Only the non-overlapping one


# ─── Constants Tests ─────────────────────────────────────────

class TestTimeframeConstants:
    """Verify timeframe constants are correct."""

    def test_valid_timeframes(self):
        assert "1m" in VALID_TIMEFRAMES
        assert "1d" in VALID_TIMEFRAMES
        assert len(VALID_TIMEFRAMES) == 7

    def test_timeframe_minutes(self):
        assert TIMEFRAME_MINUTES["1m"] == 1
        assert TIMEFRAME_MINUTES["5m"] == 5
        assert TIMEFRAME_MINUTES["1h"] == 60
        assert TIMEFRAME_MINUTES["1d"] == 1440

    def test_timeframe_requires(self):
        assert TIMEFRAME_REQUIRES["5m"] == "1m"
        assert TIMEFRAME_REQUIRES["1h"] == "15m"
        assert TIMEFRAME_REQUIRES["1d"] == "1h"


# ─── Provider Registry Tests ─────────────────────────────────

class TestProviderRegistry:
    """Tests for the provider registry."""

    def test_providers_registered(self):
        providers = ProviderRegistry.list_providers()
        assert "csv" in providers
        assert "yfinance" in providers

    def test_get_existing_provider(self):
        provider = ProviderRegistry.get("csv")
        assert provider is not None
        assert provider.name == "csv"

    def test_get_unknown_provider(self):
        provider = ProviderRegistry.get("nonexistent")
        assert provider is None


# ─── API Endpoint Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_list_providers_endpoint():
    """Verify /market-data/providers returns available providers."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/market-data/providers")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "csv" in data["providers"]
        assert "yfinance" in data["providers"]


@pytest.mark.asyncio
async def test_get_bars_missing_params():
    """Verify /market-data/bars rejects missing required params."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/market-data/bars")
        assert response.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_invalid_timeframe_rejected():
    """Verify invalid timeframe returns 400."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/market-data/bars",
            params={"instrument": "MNQ", "timeframe": "30m"},
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_timeframes_endpoint_unknown_instrument():
    """Verify timeframes endpoint rejects requests for unknown instrument.

    NOTE: This test requires a running database. If no DB is available,
    it will raise ConnectionRefusedError — this is expected in CI without
    a PostgreSQL instance. Skip if database is unavailable.
    """
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            response = await client.get(
                "/api/v1/market-data/timeframes",
                params={"instrument": "UNKNOWN"},
            )
        except ConnectionRefusedError:
            pytest.skip("Database not available — skipping DB-dependent test")
        assert response.status_code == 200
        data = response.json()
        assert data["available_timeframes"] == []
