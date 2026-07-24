"""Phase 7A Tests — Monitoring, Alerts, Audit Logs, Metrics.

Tests for health checks, alert lifecycle, audit logging, metrics,
dashboard, serialization, and API integration.
"""

import json
from datetime import datetime, timezone

import pytest

from app.services.monitoring.engine import (
    MonitoringController, HealthCheck, MetricPoint,
)
from app.services.monitoring.alerts import (
    AlertManager, Alert, AlertSeverity, AlertStatus,
)


# ─── Health Checks ────────────────────────────────────────

class TestHealthChecks:
    """Health check generation."""

    def test_system_healthy(self):
        c = MonitoringController()
        h = c.check_system()
        assert h.status == "healthy"
        assert h.component == "system"

    def test_database_healthy(self):
        c = MonitoringController()
        h = c.check_database(True)
        assert h.status == "healthy"

    def test_database_unhealthy(self):
        c = MonitoringController()
        h = c.check_database(False)
        assert h.status == "unhealthy"

    def test_broker_connected(self):
        c = MonitoringController()
        h = c.check_broker(True)
        assert h.status == "healthy"

    def test_broker_disconnected(self):
        c = MonitoringController()
        h = c.check_broker(False)
        assert h.status == "degraded"

    def test_market_data_flowing(self):
        c = MonitoringController()
        h = c.check_market_data(True)
        assert h.status == "healthy"

    def test_market_data_stalled(self):
        c = MonitoringController()
        h = c.check_market_data(False)
        assert h.status == "degraded"

    def test_run_all_checks(self):
        c = MonitoringController()
        results = c.run_all_checks()
        assert len(results) == 7
        assert results[0].component == "system"

    def test_health_summary(self):
        c = MonitoringController()
        c.run_all_checks(db_ok=True, broker_ok=False)
        summary = c.get_health_summary()
        assert summary["overall"] in ("healthy", "degraded", "unhealthy")
        assert "components" in summary

    def test_health_check_to_dict(self):
        h = HealthCheck(component="test", status="healthy", detail="OK")
        d = h.to_dict()
        assert d["component"] == "test"


# ─── Metrics ──────────────────────────────────────────────

class TestMetrics:
    """Metric collection and aggregation."""

    def test_record_metric(self):
        c = MonitoringController()
        c.record_metric("orders_per_min", 5.0)
        c.record_metric("orders_per_min", 7.0)
        metrics = c.get_metrics("orders_per_min")
        assert len(metrics) == 2
        assert metrics[0]["value"] == 5.0

    def test_get_metrics_all(self):
        c = MonitoringController()
        c.record_metric("latency", 0.1)
        c.record_metric("latency", 0.2)
        all_metrics = c.get_metrics()
        assert len(all_metrics) == 2

    def test_aggregated_metrics(self):
        c = MonitoringController()
        c.record_metric("cpu", 50.0)
        c.record_metric("cpu", 70.0)
        agg = c.get_aggregated_metrics()
        assert agg["cpu"]["avg"] == 60.0
        assert agg["cpu"]["min"] == 50.0
        assert agg["cpu"]["max"] == 70.0

    def test_empty_metrics(self):
        c = MonitoringController()
        assert c.get_aggregated_metrics() == {}
        assert c.get_metrics() == []

    def test_metric_point_to_dict(self):
        mp = MetricPoint(name="test", value=42.0, tags={"env": "prod"})
        d = mp.to_dict()
        assert d["name"] == "test"
        assert d["value"] == 42.0


# ─── Alerts ───────────────────────────────────────────────

class TestAlerts:
    """Alert lifecycle."""

    def test_create_alert(self):
        am = AlertManager()
        alert = am.create_alert("broker_down", "Broker disconnected", "critical")
        assert alert.status == "active"
        assert alert.severity == "critical"
        assert len(am.active_alerts) == 1

    def test_acknowledge_alert(self):
        am = AlertManager()
        alert = am.create_alert("latency_high", "High latency", "warning")
        updated = am.acknowledge_alert(alert.alert_id)
        assert updated.status == "acknowledged"
        assert updated.acknowledged_at is not None

    def test_resolve_alert(self):
        am = AlertManager()
        alert = am.create_alert("db_down", "DB unavailable", "critical")
        am.acknowledge_alert(alert.alert_id)
        updated = am.resolve_alert(alert.alert_id)
        assert updated.status == "resolved"

    def test_acknowledge_nonexistent(self):
        am = AlertManager()
        result = am.acknowledge_alert("nonexistent")
        assert result is None

    def test_get_alerts_filtered(self):
        am = AlertManager()
        am.create_alert("t1", "msg1", "warning")
        am.create_alert("t2", "msg2", "critical")
        active = am.get_alerts(status="active")
        assert len(active) == 2
        critical = am.get_alerts(severity="critical")
        assert len(critical) == 1

    def test_alert_summary(self):
        am = AlertManager()
        am.create_alert("t1", "msg1", "warning")
        am.create_alert("t2", "msg2", "critical")
        summary = am.get_summary()
        assert summary["total"] == 2
        assert summary["active"] == 2

    def test_alert_to_dict(self):
        alert = Alert(alert_type="test", severity="critical",
                     message="Test alert", status="active")
        d = alert.to_dict()
        assert d["alert_type"] == "test"
        assert d["severity"] == "critical"


# ─── Dashboard ────────────────────────────────────────────

class TestDashboard:
    """Dashboard data."""

    def test_dashboard_data(self):
        c = MonitoringController()
        c.run_all_checks()
        c.record_metric("latency", 0.05)
        data = c.get_dashboard_data()
        assert "health" in data
        assert "metrics" in data
        assert "timestamp" in data


# ─── Determinism ──────────────────────────────────────────

class TestDeterminism:
    """Deterministic operations."""

    def test_health_check_deterministic(self):
        c1 = MonitoringController()
        c2 = MonitoringController()
        h1 = c1.check_database(True)
        h2 = c2.check_database(True)
        assert h1.status == h2.status

    def test_alert_creation_deterministic(self):
        am1 = AlertManager()
        am2 = AlertManager()
        a1 = am1.create_alert("test", "msg", "warning")
        a2 = am2.create_alert("test", "msg", "warning")
        assert a1.status == a2.status
        assert a1.severity == a2.severity


# ─── Serialization ────────────────────────────────────────

class TestSerialization:
    """JSON serialization."""

    def test_health_check_json(self):
        h = HealthCheck(component="api", status="healthy")
        s = json.dumps(h.to_dict())
        assert "api" in s

    def test_alert_json(self):
        alert = Alert(alert_type="test", message="test")
        s = json.dumps(alert.to_dict())
        assert "active" in s


# ─── API Tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_monitoring_health_api():
    """Test /api/v1/monitoring/health endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/monitoring/health")
            assert response.status_code == 200
            data = response.json()
            assert "overall" in data
    except ConnectionRefusedError:
        pytest.skip("Database not available")


@pytest.mark.asyncio
async def test_monitoring_health_database():
    """Test /api/v1/monitoring/health/database endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/monitoring/health/database")
            assert response.status_code == 200
    except ConnectionRefusedError:
        pytest.skip("Database not available")
