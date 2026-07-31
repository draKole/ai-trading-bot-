"""Health /full endpoint — schema contract, response semantics, probe logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.monitoring import MonitoringController, HealthCheck


# ═══════════════════════════════════════════════════════════════
# HealthCheck dataclass
# ═══════════════════════════════════════════════════════════════

class TestHealthCheck:
    def test_to_dict_includes_all_fields(self):
        hc = HealthCheck(component="database", status="healthy", detail="ok", latency_ms=1.5)
        d = hc.to_dict()
        assert d["component"] == "database"
        assert d["status"] == "healthy"
        assert d["detail"] == "ok"
        assert d["latency_ms"] == 1.5
        assert "timestamp" in d

    def test_to_dict_latency_none_handled(self):
        hc = HealthCheck(component="api", status="healthy")
        d = hc.to_dict()
        assert d["latency_ms"] is None

    def test_status_values(self):
        for status in ("healthy", "degraded", "unhealthy", "unknown"):
            hc = HealthCheck(component="test", status=status)
            assert hc.status == status
            assert hc.to_dict()["status"] == status


# ═══════════════════════════════════════════════════════════════
# MonitoringController health summary logic
# ═══════════════════════════════════════════════════════════════

class TestHealthSummary:
    def test_empty_history_returns_unknown(self):
        ctrl = MonitoringController()
        summary = ctrl.get_health_summary()
        assert summary["overall"] == "unknown"
        assert summary["components"] == {}

    def test_all_healthy(self):
        ctrl = MonitoringController()
        ctrl._health_history = [
            HealthCheck("system", "healthy"),
            HealthCheck("api", "healthy"),
            HealthCheck("database", "healthy"),
        ]
        summary = ctrl.get_health_summary()
        assert summary["overall"] == "healthy"

    def test_degraded_overrides_healthy(self):
        ctrl = MonitoringController()
        ctrl._health_history = [
            HealthCheck("system", "healthy"),
            HealthCheck("redis", "degraded"),
            HealthCheck("database", "healthy"),
        ]
        summary = ctrl.get_health_summary()
        assert summary["overall"] == "degraded"

    def test_unhealthy_overrides_degraded(self):
        ctrl = MonitoringController()
        ctrl._health_history = [
            HealthCheck("system", "healthy"),
            HealthCheck("redis", "degraded"),
            HealthCheck("database", "unhealthy"),
        ]
        summary = ctrl.get_health_summary()
        assert summary["overall"] == "unhealthy"

    def test_latest_component_wins_on_duplicate(self):
        ctrl = MonitoringController()
        ctrl._health_history = [
            HealthCheck("database", "unhealthy", "first"),
            HealthCheck("database", "healthy", "second"),
        ]
        summary = ctrl.get_health_summary()
        assert summary["components"]["database"]["status"] == "healthy"
        assert summary["components"]["database"]["detail"] == "second"


# ═══════════════════════════════════════════════════════════════
# System metrics
# ═══════════════════════════════════════════════════════════════

class TestSystemMetrics:
    def test_metrics_has_all_fields(self):
        ctrl = MonitoringController()
        metrics = ctrl.get_system_metrics()
        d = metrics.to_dict()
        assert "cpu_percent" in d
        assert "memory_percent" in d
        assert "memory_used_mb" in d
        assert "memory_total_mb" in d
        assert "uptime_seconds" in d
        assert "uptime_human" in d

    def test_uptime_human_format(self):
        from app.services.monitoring.engine import SystemMetrics
        assert SystemMetrics._format_uptime(30) == "30s"
        assert SystemMetrics._format_uptime(90) == "1m 30s"
        assert SystemMetrics._format_uptime(3661) == "1h 1m"
        assert SystemMetrics._format_uptime(90000) == "1d 1h"


# ═══════════════════════════════════════════════════════════════
# Mode info
# ═══════════════════════════════════════════════════════════════

class TestModeInfo:
    def test_mode_info_keys(self):
        ctrl = MonitoringController()
        info = ctrl.get_mode_info()
        assert "mode" in info
        assert "live_allowed" in info
        assert "uptime_seconds" in info
        assert info["mode"] in ("PAPER", "BACKTEST", "LIVE")


# ═══════════════════════════════════════════════════════════════
# Trading status
# ═══════════════════════════════════════════════════════════════

class TestTradingStatus:
    def test_default_status_is_zero(self):
        ctrl = MonitoringController()
        ts = ctrl.get_trading_status()
        assert ts.active_positions == 0
        assert ts.open_orders == 0
        assert ts.signals_today == 0
        assert ts.trades_today == 0

    def test_update_trading_status_partial(self):
        ctrl = MonitoringController()
        ctrl.update_trading_status(active_positions=3)
        ts = ctrl.get_trading_status()
        assert ts.active_positions == 3
        assert ts.open_orders == 0  # unchanged

    def test_update_trading_status_all(self):
        ctrl = MonitoringController()
        ctrl.update_trading_status(
            active_positions=2, open_orders=1,
            signals_today=10, trades_today=5,
        )
        ts = ctrl.get_trading_status()
        d = ts.to_dict()
        assert d == {
            "active_positions": 2,
            "open_orders": 1,
            "signals_today": 10,
            "trades_today": 5,
        }


# ═══════════════════════════════════════════════════════════════
# Sync health checks (fast, no probes)
# ═══════════════════════════════════════════════════════════════

class TestSyncChecks:
    def test_check_system_always_healthy(self):
        ctrl = MonitoringController()
        hc = ctrl.check_system()
        assert hc.status == "healthy"
        assert hc.component == "system"

    def test_check_api_always_healthy(self):
        ctrl = MonitoringController()
        hc = ctrl.check_api()
        assert hc.status == "healthy"
        assert hc.component == "api"

    def test_check_database_healthy(self):
        ctrl = MonitoringController()
        hc = ctrl.check_database(db_available=True)
        assert hc.status == "healthy"

    def test_check_database_unhealthy(self):
        ctrl = MonitoringController()
        hc = ctrl.check_database(db_available=False)
        assert hc.status == "unhealthy"

    def test_check_redis_degraded_when_unavailable(self):
        ctrl = MonitoringController()
        hc = ctrl.check_redis(redis_available=False)
        assert hc.status == "degraded"

    def test_run_all_checks_returns_nine_components(self):
        ctrl = MonitoringController()
        results = ctrl.run_all_checks()
        assert len(results) == 9
        components = {r.component for r in results}
        assert "system" in components
        assert "api" in components
        assert "database" in components
        assert "redis" in components
        assert "broker" in components
        assert "market_data" in components
        assert "live_trading" in components
        assert "paper_trading" in components
        assert "workers" in components


# ═══════════════════════════════════════════════════════════════
# Dashboard data completeness
# ═══════════════════════════════════════════════════════════════

class TestDashboardData:
    def test_dashboard_data_keys(self):
        ctrl = MonitoringController()
        ctrl._health_history = [HealthCheck("system", "healthy")]
        data = ctrl.get_dashboard_data()
        assert "health" in data
        assert "metrics" in data
        assert "system" in data
        assert "mode" in data
        assert "trading" in data
        assert "timestamp" in data
