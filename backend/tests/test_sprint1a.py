"""Sprint 1a Tests — Production Monitoring Engine.

Tests for async health probes (PostgreSQL, Redis, broker, market data, workers),
system metrics (CPU, memory, uptime), trading status, probe registration,
dashboard data extension, and serialization.
"""

import json
import time
from datetime import datetime, timezone

import pytest

from app.services.monitoring.engine import (
    MonitoringController,
    HealthCheck,
    MetricPoint,
    SystemMetrics,
    TradingStatus,
)


# ─── Probe Registration ──────────────────────────────────


class TestProbeRegistration:
    """Async probe registration and invocation."""

    async def _true_probe(self) -> bool:
        return True

    async def _false_probe(self) -> bool:
        return False

    async def _error_probe(self) -> bool:
        raise RuntimeError("Simulated probe failure")

    @pytest.mark.asyncio
    async def test_db_probe_healthy(self):
        c = MonitoringController()
        c.register_db_probe(self._true_probe)
        result = await c.probe_database()
        assert result.component == "database"
        assert result.status == "healthy"
        assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_db_probe_unhealthy(self):
        c = MonitoringController()
        c.register_db_probe(self._false_probe)
        result = await c.probe_database()
        assert result.status == "unhealthy"

    @pytest.mark.asyncio
    async def test_db_probe_error_handling(self):
        c = MonitoringController()
        c.register_db_probe(self._error_probe)
        result = await c.probe_database()
        assert result.status == "unhealthy"
        assert "Simulated" in result.detail

    @pytest.mark.asyncio
    async def test_db_probe_unregistered(self):
        c = MonitoringController()
        result = await c.probe_database()
        assert result.status == "unhealthy"
        assert "No database probe" in result.detail

    @pytest.mark.asyncio
    async def test_redis_probe(self):
        c = MonitoringController()
        c.register_redis_probe(self._true_probe)
        result = await c.probe_redis()
        assert result.component == "redis"
        assert result.status == "healthy"

    @pytest.mark.asyncio
    async def test_redis_probe_degraded(self):
        c = MonitoringController()
        c.register_redis_probe(self._false_probe)
        result = await c.probe_redis()
        assert result.status == "degraded"

    @pytest.mark.asyncio
    async def test_broker_probe(self):
        c = MonitoringController()
        c.register_broker_probe(self._true_probe)
        result = await c.probe_broker()
        assert result.component == "broker"
        assert result.status == "healthy"

    @pytest.mark.asyncio
    async def test_broker_probe_unregistered(self):
        c = MonitoringController()
        result = await c.probe_broker()
        assert result.status == "degraded"
        assert "No broker probe" in result.detail

    @pytest.mark.asyncio
    async def test_market_data_probe(self):
        c = MonitoringController()
        c.register_market_data_probe(self._true_probe)
        result = await c.probe_market_data()
        assert result.component == "market_data"
        assert result.status == "healthy"

    @pytest.mark.asyncio
    async def test_workers_probe(self):
        c = MonitoringController()
        c.register_worker_heartbeat_probe(self._true_probe)
        result = await c.probe_workers()
        assert result.component == "workers"
        assert result.status == "healthy"


# ─── Run All Probes ──────────────────────────────────────


class TestRunAllProbes:
    """Full probe execution."""

    async def _true_probe(self) -> bool:
        return True

    async def _false_probe(self) -> bool:
        return False

    @pytest.mark.asyncio
    async def test_run_all_probes(self):
        c = MonitoringController()
        c.register_db_probe(self._true_probe)
        c.register_redis_probe(self._true_probe)
        c.register_broker_probe(self._false_probe)
        c.register_market_data_probe(self._true_probe)
        c.register_worker_heartbeat_probe(self._true_probe)
        results = await c.run_all_probes()
        assert len(results) == 7  # system, api, db, redis, broker, market, workers
        components = {r.component for r in results}
        assert "system" in components
        assert "database" in components
        assert "redis" in components
        assert "broker" in components
        assert "market_data" in components
        assert "workers" in components

    @pytest.mark.asyncio
    async def test_run_all_probes_persists_history(self):
        c = MonitoringController()
        c.register_db_probe(self._true_probe)
        c.register_redis_probe(self._true_probe)
        c.register_broker_probe(self._false_probe)
        c.register_market_data_probe(self._true_probe)
        c.register_worker_heartbeat_probe(self._true_probe)
        await c.run_all_probes()
        summary = c.get_health_summary()
        assert summary["overall"] in ("healthy", "degraded", "unhealthy")


# ─── System Metrics ──────────────────────────────────────


class TestSystemMetrics:
    """System metrics collection."""

    def test_system_metrics_present(self):
        c = MonitoringController()
        metrics = c.get_system_metrics()
        assert isinstance(metrics, SystemMetrics)
        assert metrics.uptime_seconds >= 0
        # CPU and memory may be 0 in sandbox, but fields must exist
        d = metrics.to_dict()
        assert "cpu_percent" in d
        assert "memory_percent" in d
        assert "uptime_seconds" in d
        assert "uptime_human" in d

    def test_system_metrics_uptime_increases(self):
        c = MonitoringController()
        m1 = c.get_system_metrics()
        time.sleep(0.5)
        m2 = c.get_system_metrics()
        assert m2.uptime_seconds > m1.uptime_seconds

    def test_format_uptime(self):
        assert SystemMetrics._format_uptime(30) == "30s"
        assert SystemMetrics._format_uptime(90) == "1m 30s"
        assert SystemMetrics._format_uptime(3661) == "1h 1m"
        assert SystemMetrics._format_uptime(90061) == "1d 1h"


# ─── Trading Status ──────────────────────────────────────


class TestTradingStatus:
    """Trading status tracking."""

    def test_default_trading_status(self):
        c = MonitoringController()
        status = c.get_trading_status()
        assert status.active_positions == 0
        assert status.open_orders == 0
        assert status.signals_today == 0
        assert status.trades_today == 0

    def test_update_trading_status(self):
        c = MonitoringController()
        c.update_trading_status(active_positions=3, open_orders=2)
        status = c.get_trading_status()
        assert status.active_positions == 3
        assert status.open_orders == 2
        # Unchanged fields retain defaults
        assert status.signals_today == 0
        assert status.trades_today == 0

    def test_update_partial(self):
        c = MonitoringController()
        c.update_trading_status(signals_today=15, trades_today=8)
        status = c.get_trading_status()
        assert status.signals_today == 15
        assert status.trades_today == 8
        assert status.active_positions == 0


# ─── Mode Info ───────────────────────────────────────────


class TestModeInfo:
    """Trading mode information."""

    def test_mode_present(self):
        c = MonitoringController()
        info = c.get_mode_info()
        assert "mode" in info
        assert "live_allowed" in info
        assert "uptime_seconds" in info
        assert info["mode"] in ("BACKTEST", "PAPER", "LIVE")

    def test_mode_property(self):
        c = MonitoringController()
        assert c.mode in ("BACKTEST", "PAPER", "LIVE")


# ─── Dashboard Data Extended ─────────────────────────────


class TestDashboardDataExtended:
    """Dashboard data includes new fields."""

    async def _true_probe(self) -> bool:
        return True

    @pytest.mark.asyncio
    async def test_dashboard_has_all_sections(self):
        c = MonitoringController()
        c.register_db_probe(self._true_probe)
        c.register_redis_probe(self._true_probe)
        c.register_broker_probe(self._true_probe)
        c.register_market_data_probe(self._true_probe)
        c.register_worker_heartbeat_probe(self._true_probe)
        await c.run_all_probes()
        data = c.get_dashboard_data()
        assert "health" in data
        assert "metrics" in data
        assert "system" in data
        assert "mode" in data
        assert "trading" in data
        assert "timestamp" in data

    def test_dashboard_trading_defaults(self):
        c = MonitoringController()
        data = c.get_dashboard_data()
        trading = data["trading"]
        assert trading["active_positions"] == 0
        assert trading["open_orders"] == 0
        assert trading["signals_today"] == 0
        assert trading["trades_today"] == 0


# ─── Health Check Latency ────────────────────────────────


class TestHealthCheckLatency:
    """Latency tracking in health checks."""

    async def _slow_probe(self) -> bool:
        import asyncio
        await asyncio.sleep(0.05)
        return True

    @pytest.mark.asyncio
    async def test_probe_records_latency(self):
        c = MonitoringController()
        c.register_db_probe(self._slow_probe)
        result = await c.probe_database()
        assert result.latency_ms is not None
        assert result.latency_ms > 0

    def test_sync_check_no_latency(self):
        c = MonitoringController()
        result = c.check_system()
        assert result.latency_ms is None


# ─── Backward Compatibility ──────────────────────────────


class TestBackwardCompatibility:
    """Existing sync check methods still work."""

    def test_run_all_checks_still_works(self):
        c = MonitoringController()
        results = c.run_all_checks()
        assert len(results) == 9  # system, api, db, redis, broker, market, live, paper, workers

    def test_check_system(self):
        c = MonitoringController()
        h = c.check_system()
        assert h.status == "healthy"

    def test_check_api(self):
        c = MonitoringController()
        h = c.check_api()
        assert h.status == "healthy"
        assert h.component == "api"

    def test_check_database(self):
        c = MonitoringController()
        h = c.check_database(True)
        assert h.status == "healthy"
        h2 = c.check_database(False)
        assert h2.status == "unhealthy"

    def test_check_redis(self):
        c = MonitoringController()
        h = c.check_redis(True)
        assert h.status == "healthy"
        h2 = c.check_redis(False)
        assert h2.status == "degraded"

    def test_check_workers(self):
        c = MonitoringController()
        h = c.check_workers(True)
        assert h.status == "healthy"


# ─── Serialization ───────────────────────────────────────


class TestSerialization:
    """All new types serialize to JSON."""

    def test_system_metrics_json(self):
        sm = SystemMetrics(cpu_percent=45.2, memory_percent=62.1,
                           uptime_seconds=3600.0)
        s = json.dumps(sm.to_dict())
        assert "45.2" in s or "45" in s

    def test_trading_status_json(self):
        ts = TradingStatus(active_positions=2, open_orders=1,
                          signals_today=25, trades_today=10)
        s = json.dumps(ts.to_dict())
        assert "2" in s
        assert "25" in s

    def test_health_check_with_latency_json(self):
        h = HealthCheck(component="test", status="healthy",
                       detail="OK", latency_ms=1.5)
        d = h.to_dict()
        assert d["latency_ms"] == 1.5
        s = json.dumps(d)
        assert "latency_ms" in s


# ─── Trading Status Counters ─────────────────────────────


class TestTradingCounters:
    """Async counter registration for trading status."""

    @pytest.mark.asyncio
    async def test_refresh_trading_status(self):
        async def pos(): return 3
        async def ord(): return 1
        async def sig(): return 42
        async def trd(): return 18
        c = MonitoringController()
        c.register_position_counter(pos)
        c.register_order_counter(ord)
        c.register_signal_counter(sig)
        c.register_trade_counter(trd)
        await c._refresh_trading_status()
        status = c.get_trading_status()
        assert status.active_positions == 3
        assert status.open_orders == 1
        assert status.signals_today == 42
        assert status.trades_today == 18

    @pytest.mark.asyncio
    async def test_counter_error_handling(self):
        async def failing(): return 1 / 0  # will raise
        c = MonitoringController()
        c.register_position_counter(failing)
        c.update_trading_status(active_positions=5)
        # Should not raise
        await c._refresh_trading_status()
        status = c.get_trading_status()
        assert status.active_positions == 5  # unchanged by failed counter


# ─── Determinism ─────────────────────────────────────────


class TestDeterminism:
    """Deterministic behavior."""

    def test_health_check_deterministic(self):
        c1 = MonitoringController()
        c2 = MonitoringController()
        h1 = c1.check_database(True)
        h2 = c2.check_database(True)
        assert h1.status == h2.status

    def test_alert_creation_deterministic(self):
        from app.services.monitoring.alerts import AlertManager
        am1 = AlertManager()
        am2 = AlertManager()
        a1 = am1.create_alert("test", "msg", "warning")
        a2 = am2.create_alert("test", "msg", "warning")
        assert a1.status == a2.status
        assert a1.severity == a2.severity


# ─── Sprint 1b API Tests ────────────────────────────────

@pytest.mark.asyncio
async def test_api_health_returns_dashboard():
    """GET /monitoring/health returns full dashboard structure."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/health")
        assert response.status_code == 200
        data = response.json()
        assert "health" in data
        assert "system" in data
        assert "mode" in data
        assert "trading" in data


@pytest.mark.asyncio
async def test_api_monitoring_status():
    """GET /monitoring/status returns consolidated status."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/status")
        assert response.status_code == 200
        data = response.json()
        assert "health" in data
        assert "system" in data
        assert "trading" in data


@pytest.mark.asyncio
async def test_api_health_database():
    """GET /health/database returns component health."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/health/database")
        assert response.status_code == 200
        data = response.json()
        assert data["component"] == "database"
        assert data["status"] in ("healthy", "unhealthy", "degraded", "unknown")


@pytest.mark.asyncio
async def test_api_health_redis():
    """GET /health/redis returns component health."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/health/redis")
        assert response.status_code == 200
        data = response.json()
        assert data["component"] == "redis"


@pytest.mark.asyncio
async def test_api_health_broker():
    """GET /health/broker returns component health."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/health/broker")
        assert response.status_code == 200
        data = response.json()
        assert data["component"] == "broker"


@pytest.mark.asyncio
async def test_api_health_market_data():
    """GET /health/market-data returns component health."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/health/market-data")
        assert response.status_code == 200
        data = response.json()
        assert data["component"] == "market_data"


@pytest.mark.asyncio
async def test_api_health_workers():
    """GET /health/workers returns component health."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/health/workers")
        assert response.status_code == 200
        data = response.json()
        assert data["component"] == "workers"


@pytest.mark.asyncio
async def test_api_health_system():
    """GET /health/system returns system info with mode and metrics."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/health/system")
        assert response.status_code == 200
        data = response.json()
        assert "system" in data
        assert "system_metrics" in data
        assert "mode" in data
        assert data["mode"]["mode"] in ("BACKTEST", "PAPER", "LIVE")


@pytest.mark.asyncio
async def test_api_alerts():
    """GET /alerts returns alerts and summary."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/alerts")
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "summary" in data


@pytest.mark.asyncio
async def test_api_dashboard():
    """GET /dashboard returns combined dashboard data."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/monitoring/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "health" in data
        assert "alerts" in data
