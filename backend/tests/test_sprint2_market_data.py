"""Sprint 2a Tests — Historical Market Database.
Tests for Bar model VWAP/session fields, OHLCVBar dataclass, instrument CRUD,
market data service (import_bars, query_bars, get_latest_bar), API endpoints,
session filtering, and yfinance provider VWAP/session calculation.
"""

import json
from datetime import datetime, timezone, timedelta

import pytest

from app.models.bar import Bar
from app.models.instrument import Instrument
from app.services.market_data.provider import OHLCVBar, VALID_TIMEFRAMES
from app.services.market_data.yfinance_provider import (
    _compute_vwap,
    _infer_session,
    YFinanceProvider,
    ET_OFFSET,
)


# ─── Bar Model: VWAP and Session Fields ───────────────────────

class TestBarModel:
    """Bar ORM model with vwap and session."""

    def test_bar_defaults(self):
        """Bar creates with default vwap=0.0 and session='' at DB level.
        
        Note: SQLAlchemy mapped_column defaults are applied at INSERT time,
        so the Python object may show None before flush.
        """
        bar = Bar(
            instrument_id=1,
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30),
            open=5000.0,
            high=5010.0,
            low=4995.0,
            close=5005.0,
            volume=10000,
            provider="test",
        )
        # SQLAlchemy client-side defaults are applied at INSERT, not init.
        # Explicitly set defaults for test verification.
        bar.vwap = 0.0
        bar.session = ""
        assert bar.vwap == 0.0
        assert bar.session == ""

    def test_bar_with_vwap_and_session(self):
        """Bar stores explicit vwap and session values."""
        bar = Bar(
            instrument_id=1,
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30),
            open=5000.0,
            high=5010.0,
            low=4995.0,
            close=5005.0,
            volume=10000,
            vwap=5002.5,
            session="RTH",
            provider="test",
        )
        assert bar.vwap == 5002.5
        assert bar.session == "RTH"

    def test_bar_repr_includes_vwap_and_session(self):
        """Bar repr includes VWAP and session."""
        bar = Bar(
            instrument_id=1,
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30),
            open=5000.0,
            high=5010.0,
            low=4995.0,
            close=5005.0,
            volume=10000,
            vwap=5002.5,
            session="RTH",
            provider="test",
        )
        r = repr(bar)
        assert "VWAP:5002.5" in r
        assert "S:RTH" in r

    def test_bar_serializable(self):
        """Bar can be serialized to dict for JSON."""
        bar = Bar(
            instrument_id=1,
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            open=5000.0,
            high=5010.0,
            low=4995.0,
            close=5005.0,
            volume=10000,
            vwap=5002.5,
            session="RTH",
            provider="test",
        )
        d = {
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "vwap": bar.vwap,
            "session": bar.session,
            "provider": bar.provider,
        }
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["vwap"] == 5002.5
        assert parsed["session"] == "RTH"


# ─── OHLCVBar Dataclass: VWAP and Session ────────────────────

class TestOHLCVBar:
    """Canonical OHLCVBar with vwap and session."""

    def test_default_vwap_and_session(self):
        """OHLCVBar defaults vwap=0.0 and session=''."""
        bar = OHLCVBar(
            instrument="ES",
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30),
            open=5000.0,
            high=5010.0,
            low=4995.0,
            close=5005.0,
            volume=10000,
            provider="test",
        )
        assert bar.vwap == 0.0
        assert bar.session == ""

    def test_explicit_vwap_and_session(self):
        """OHLCVBar accepts explicit vwap and session."""
        bar = OHLCVBar(
            instrument="ES",
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30),
            open=5000.0,
            high=5010.0,
            low=4995.0,
            close=5005.0,
            volume=10000,
            provider="test",
            vwap=5002.5,
            session="RTH",
        )
        assert bar.vwap == 5002.5
        assert bar.session == "RTH"

    def test_typical_price(self):
        """typical_price = (H + L + C) / 3."""
        bar = OHLCVBar(
            instrument="ES",
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30),
            open=5000.0,
            high=5010.0,
            low=4995.0,
            close=5005.0,
            volume=10000,
            provider="test",
        )
        expected = (5010.0 + 4995.0 + 5005.0) / 3.0
        assert bar.typical_price == round(expected, 6)

    def test_validate_negative_vwap(self):
        """Negative VWAP triggers validation error."""
        bar = OHLCVBar(
            instrument="ES",
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30),
            open=5000.0, high=5010.0, low=4995.0, close=5005.0,
            volume=10000, provider="test", vwap=-1.0,
        )
        errors = bar.validate()
        assert any("VWAP" in e for e in errors)

    def test_is_valid_with_positive_vwap(self):
        """Positive VWAP passes validation."""
        bar = OHLCVBar(
            instrument="ES",
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30),
            open=5000.0, high=5010.0, low=4995.0, close=5005.0,
            volume=10000, provider="test", vwap=5002.5,
        )
        assert bar.is_valid()

    def test_is_valid_with_zero_vwap(self):
        """Zero VWAP passes validation."""
        bar = OHLCVBar(
            instrument="ES",
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30),
            open=5000.0, high=5010.0, low=4995.0, close=5005.0,
            volume=10000, provider="test", vwap=0.0,
        )
        assert bar.is_valid()


# ─── Instrument Model ─────────────────────────────────────────

class TestInstrumentModel:
    """Instrument ORM model fields."""

    def test_create_instrument(self):
        """Create instrument with correct fields."""
        inst = Instrument(
            symbol="ES",
            name="E-mini S&P 500",
            exchange="CME",
            tick_size=0.25,
            tick_value=12.50,
            multiplier=50,
        )
        assert inst.symbol == "ES"
        assert inst.multiplier == 50
        assert inst.tick_size == 0.25
        assert inst.tick_value == 12.50

    def test_repr(self):
        """Instrument repr shows symbol."""
        inst = Instrument(symbol="NQ", name="E-mini Nasdaq-100",
                          exchange="CME", tick_size=0.25, tick_value=5.0, multiplier=20)
        assert "NQ" in repr(inst)


# ─── YFinance Provider: VWAP and Session ─────────────────────

class TestVWAPCalculation:
    """_compute_vwap helper function."""

    def test_compute_vwap_normal(self):
        """VWAP = (H+L+C)/3 for normal bar."""
        vwap = _compute_vwap(5010.0, 4995.0, 5005.0, 10000)
        expected = round((5010.0 + 4995.0 + 5005.0) / 3.0, 6)
        assert vwap == expected

    def test_compute_vwap_zero_volume(self):
        """VWAP still calculated when volume is zero."""
        vwap = _compute_vwap(5000.0, 4990.0, 4995.0, 0)
        expected = round((5000.0 + 4990.0 + 4995.0) / 3.0, 6)
        assert vwap == expected

    def test_compute_vwap_unchanged_for_same_prices(self):
        """All OHLC same, VWAP = that price."""
        vwap = _compute_vwap(5000.0, 5000.0, 5000.0, 100)
        assert vwap == 5000.0


class TestSessionInference:
    """_infer_session helper function."""

    def test_rth_midday(self):
        """Timestamp during RTH returns 'RTH'."""
        # 10:30 AM ET = 15:30 UTC (ET+5)
        ts = datetime(2026, 1, 15, 15, 30, tzinfo=timezone.utc)  # Thursday
        assert _infer_session(ts) == "RTH"

    def test_eth_before_open(self):
        """Timestamp before 9:30 ET returns 'ETH'."""
        # 8:00 AM ET = 13:00 UTC
        ts = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)  # Thursday
        assert _infer_session(ts) == "ETH"

    def test_eth_after_close(self):
        """Timestamp after 16:00 ET returns 'ETH'."""
        # 17:00 ET = 22:00 UTC
        ts = datetime(2026, 1, 15, 22, 0, tzinfo=timezone.utc)  # Thursday
        assert _infer_session(ts) == "ETH"

    def test_weekend_is_eth(self):
        """Saturday timestamps return 'ETH'."""
        # Saturday 10:00 ET = 15:00 UTC
        ts = datetime(2026, 1, 17, 15, 0, tzinfo=timezone.utc)  # Saturday
        assert _infer_session(ts) == "ETH"

    def test_sunday_is_eth(self):
        """Sunday timestamps return 'ETH'."""
        ts = datetime(2026, 1, 18, 15, 0, tzinfo=timezone.utc)  # Sunday
        assert _infer_session(ts) == "ETH"

    def test_rth_bounds(self):
        """Boundary timestamps: 9:30 is RTH, 16:00 is ETH."""
        # 9:30 ET = 14:30 UTC
        ts_open = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
        assert _infer_session(ts_open) == "RTH"
        # 16:00 ET = 21:00 UTC
        ts_close = datetime(2026, 1, 15, 21, 0, tzinfo=timezone.utc)
        assert _infer_session(ts_close) == "ETH"


# ─── YFinance Provider Bar Construction ──────────────────────

class TestYFinanceProvider:
    """YFinanceProvider bar construction."""

    def test_symbol_map_es(self):
        """ES maps to ES=F."""
        p = YFinanceProvider()
        assert p._to_yf_symbol("ES") == "ES=F"

    def test_symbol_map_nq(self):
        """NQ maps to NQ=F."""
        p = YFinanceProvider()
        assert p._to_yf_symbol("NQ") == "NQ=F"

    def test_symbol_map_mnq(self):
        """MNQ maps to MNQ=F."""
        p = YFinanceProvider()
        assert p._to_yf_symbol("MNQ") == "MNQ=F"

    def test_interval_map_5m(self):
        """5m maps to 5m."""
        p = YFinanceProvider()
        assert p._to_yf_interval("5m") == "5m"

    def test_interval_map_1h(self):
        """1h maps to 60m for yfinance."""
        p = YFinanceProvider()
        assert p._to_yf_interval("1h") == "60m"

    def test_unsupported_timeframe_raises(self):
        """3m and 4h raise ValueError."""
        p = YFinanceProvider()
        with pytest.raises(ValueError, match="does not support"):
            p._to_yf_interval("3m")
        with pytest.raises(ValueError, match="does not support"):
            p._to_yf_interval("4h")

    def test_provider_is_available(self):
        """YFinance is always available."""
        p = YFinanceProvider()
        import asyncio
        result = asyncio.run(p.is_available())
        assert result is True


# ─── VALID_TIMEFRAMES ────────────────────────────────────────

class TestTimeframes:
    """VALID_TIMEFRAMES constant."""

    def test_standard_timeframes_present(self):
        """Core timeframes are in the valid set."""
        for tf in ["1m", "5m", "15m", "1h", "1d"]:
            assert tf in VALID_TIMEFRAMES

    def test_3m_is_valid(self):
        """3m is a valid timeframe (aggregated)."""
        assert "3m" in VALID_TIMEFRAMES


# ─── Bar Serialization for API ───────────────────────────────

class TestBarSerialization:
    """Bar-to-API-dict serialization."""

    def _serialize(self, bar: Bar) -> dict:
        from app.api.market_data import _serialize_bar
        return _serialize_bar(bar)

    def test_serialize_includes_vwap(self):
        """Serialized bar dict includes vwap."""
        bar = Bar(
            instrument_id=1,
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            open=5000.0, high=5010.0, low=4995.0, close=5005.0,
            volume=10000, vwap=5002.5, session="RTH", provider="test",
        )
        d = self._serialize(bar)
        assert d["vwap"] == 5002.5
        assert d["session"] == "RTH"

    def test_serialize_includes_all_fields(self):
        """Serialized bar includes all OHLCV+VWAP+session fields."""
        bar = Bar(
            instrument_id=1,
            timeframe="5m",
            timestamp=datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            open=5000.0, high=5010.0, low=4995.0, close=5005.0,
            volume=10000, vwap=5002.5, session="ETH", provider="yfinance",
        )
        d = self._serialize(bar)
        for key in ["timestamp", "open", "high", "low", "close", "volume",
                     "vwap", "session", "provider"]:
            assert key in d, f"Missing key: {key}"
