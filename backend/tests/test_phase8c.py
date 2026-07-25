"""Phase 8C Tests — Multi-Market Scanner & Opportunity Ranking."""

import json
import pytest
from app.services.scanner.engine import (
    ScannerController, WatchlistEntry, ScanOpportunity,
    score_opportunity, confidence_label,
)


class TestScoring:
    def test_score_basic(self):
        data = {"confluence": 80, "structure": 70, "liquidity": 60,
                "fvg": 50, "trend": 40, "session": 30, "volume": 20}
        s = score_opportunity(data)
        assert 0 <= s <= 100

    def test_score_max(self):
        data = {k: 100 for k in ["confluence","structure","liquidity","fvg","trend","session","volume"]}
        assert score_opportunity(data) == 100.0

    def test_score_min(self):
        assert score_opportunity({}) == 0.0

    def test_confidence_labels(self):
        assert confidence_label(85) == "Very High"
        assert confidence_label(70) == "High"
        assert confidence_label(55) == "Medium"
        assert confidence_label(40) == "Low"
        assert confidence_label(20) == "Very Low"


class TestWatchlist:
    def test_create(self):
        c = ScannerController()
        wl = c.create_watchlist("Futures", ["ES", "NQ"], ["5m", "15m"])
        assert wl.name == "Futures"
        assert len(wl.symbols) == 2

    def test_list(self):
        c = ScannerController()
        c.create_watchlist("A", ["ES"])
        c.create_watchlist("B", ["NQ"])
        assert len(c.list_watchlists()) == 2

    def test_get(self):
        c = ScannerController()
        c.create_watchlist("Test", ["ES"])
        wl = c.get_watchlist("Test")
        assert wl is not None

    def test_get_nonexistent(self):
        c = ScannerController()
        assert c.get_watchlist("nonexistent") is None


class TestScan:
    def test_scan_empty_watchlist(self):
        c = ScannerController()
        results = c.scan("nonexistent")
        assert results == []

    def test_scan_with_data(self):
        c = ScannerController()
        c.create_watchlist("Futures", ["ES", "NQ"], ["5m"])
        data = {
            "ES": {"5m": {"confluence": 80, "direction": "bullish"}},
            "NQ": {"5m": {"confluence": 40, "direction": "bearish"}},
        }
        results = c.scan("Futures", data)
        assert len(results) == 2
        assert results[0].rank == 1  # Higher score first

    def test_ranking(self):
        c = ScannerController()
        c.create_watchlist("Test", ["A", "B", "C"], ["5m"])
        data = {
            "A": {"5m": {"confluence": 30}},
            "B": {"5m": {"confluence": 90}},
            "C": {"5m": {"confluence": 60}},
        }
        results = c.scan("Test", data)
        assert results[0].symbol == "B"  # Highest score
        assert results[2].symbol == "A"  # Lowest score

    def test_top_n(self):
        c = ScannerController()
        c.create_watchlist("Test", ["A", "B", "C", "D"], ["5m"])
        data = {s: {"5m": {"confluence": i*25}} for i, s in enumerate(["A","B","C","D"])}
        top = c.get_top_opportunities("Test", 2, data)
        assert len(top) == 2

    def test_large_watchlist(self):
        """500+ symbols."""
        c = ScannerController()
        symbols = [f"S{i}" for i in range(500)]
        c.create_watchlist("Large", symbols, ["5m"])
        results = c.scan("Large")
        assert len(results) == 500

    def test_statistics(self):
        c = ScannerController()
        c.create_watchlist("T", ["ES"], ["5m"])
        c.scan("T")
        stats = c.get_statistics()
        assert stats["total_scans"] == 1


class TestSerialization:
    def test_watchlist_to_dict(self):
        wl = WatchlistEntry("Test", "desc", ["ES"], ["5m"])
        d = wl.to_dict()
        assert d["name"] == "Test"
        assert d["symbol_count"] == 1

    def test_opportunity_to_dict(self):
        o = ScanOpportunity(symbol="ES", timeframe="5m", score=75, rank=1)
        d = o.to_dict()
        assert d["symbol"] == "ES"
        assert d["rank"] == 1


@pytest.mark.asyncio
async def test_scanner_watchlists_api():
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/scanner/watchlists")
            assert resp.status_code == 200
    except ConnectionRefusedError:
        pytest.skip("Database not available")
