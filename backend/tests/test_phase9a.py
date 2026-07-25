"""Phase 9A Tests — Operator Dashboard & Command Center."""

import json
from datetime import datetime, timezone, timedelta
import pytest
from app.services.dashboard.engine import (
    DashboardController, TimelineEvent, WidgetData,
)


class TestSystemOverview:
    def test_default(self):
        c = DashboardController()
        result = c.system_overview()
        assert result["overall_status"] == "healthy"
        assert result["health"]["counts"] == {"healthy": 0, "degraded": 0, "unhealthy": 0}
        assert result["broker"] == {"connected": False, "accounts": 0}
        assert result["alerts"] == 0

    def test_healthy_services(self):
        c = DashboardController()
        health = [{"name": "db", "status": "healthy"}, {"name": "redis", "status": "healthy"}]
        result = c.system_overview(health_statuses=health)
        assert result["overall_status"] == "healthy"
        assert result["health"]["counts"]["healthy"] == 2

    def test_degraded(self):
        c = DashboardController()
        health = [{"name": "db", "status": "healthy"}, {"name": "redis", "status": "degraded"}]
        result = c.system_overview(health_statuses=health)
        assert result["overall_status"] == "degraded"

    def test_unhealthy(self):
        c = DashboardController()
        health = [{"name": "db", "status": "healthy"}, {"name": "redis", "status": "unhealthy"}]
        result = c.system_overview(health_statuses=health)
        assert result["overall_status"] == "unhealthy"

    def test_broker_connected(self):
        c = DashboardController()
        result = c.system_overview(broker_status={"connected": True, "accounts": 3})
        assert result["broker"]["connected"] is True
        assert result["broker"]["accounts"] == 3

    def test_active_alerts_count(self):
        c = DashboardController()
        alerts = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = c.system_overview(active_alerts=alerts)
        assert result["alerts"] == 3

    def test_uptime_version(self):
        c = DashboardController()
        result = c.system_overview(uptime_seconds=3600.5, version="2.1.0", environment="staging",
                                    session_status="pre-market")
        assert result["uptime_seconds"] == 3600.5
        assert result["version"] == "2.1.0"
        assert result["environment"] == "staging"
        assert result["session"] == "pre-market"


class TestTradingOverview:
    def test_default(self):
        c = DashboardController()
        result = c.trading_overview()
        assert result["open_positions_count"] == 0
        assert result["pending_orders_count"] == 0
        assert result["daily_pnl"] == 0.0

    def test_with_positions(self):
        c = DashboardController()
        positions = [{"symbol": "ES", "qty": 2}, {"symbol": "NQ", "qty": -1}]
        result = c.trading_overview(positions=positions)
        assert result["open_positions_count"] == 2

    def test_pending_orders(self):
        c = DashboardController()
        orders = [
            {"id": 1, "status": "pending"},
            {"id": 2, "status": "filled"},
            {"id": 3, "status": "pending"},
        ]
        result = c.trading_overview(orders=orders)
        assert result["pending_orders_count"] == 2
        assert result["filled_orders_today"] == 1

    def test_pnl_rounding(self):
        c = DashboardController()
        result = c.trading_overview(daily_pnl=123.456, unrealized_pnl=-50.123)
        assert result["daily_pnl"] == 123.46
        assert result["unrealized_pnl"] == -50.12

    def test_exposure_risk(self):
        c = DashboardController()
        result = c.trading_overview(
            portfolio_equity=100000, buying_power=200000,
            risk_utilization_pct=25.5, exposure_pct=45.0,
        )
        assert result["portfolio_equity"] == 100000
        assert result["buying_power"] == 200000
        assert result["risk_utilization_pct"] == 25.5
        assert result["exposure_pct"] == 45.0


class TestScannerDashboard:
    def test_default(self):
        c = DashboardController()
        result = c.scanner_dashboard()
        assert result["active_opportunities"] == 0
        assert result["watchlist_count"] == 0

    def test_with_opportunities(self):
        c = DashboardController()
        opps = [
            {"symbol": "ES", "score": 85},
            {"symbol": "NQ", "score": 40},
            {"symbol": "CL", "score": 60},
        ]
        result = c.scanner_dashboard(opportunities=opps)
        assert result["active_opportunities"] == 3
        assert len(result["top_opportunities"]) == 3
        assert result["top_opportunities"][0]["symbol"] == "ES"  # highest score first

    def test_avg_confidence(self):
        c = DashboardController()
        opps = [{"score": 80}, {"score": 40}]
        result = c.scanner_dashboard(opportunities=opps)
        assert result["avg_confidence"] == 60.0

    def test_avg_confidence_empty(self):
        c = DashboardController()
        result = c.scanner_dashboard(opportunities=[])
        assert result["avg_confidence"] == 0.0

    def test_watchlist_count(self):
        c = DashboardController()
        result = c.scanner_dashboard(watchlists=[{"name": "a"}, {"name": "b"}, {"name": "c"}])
        assert result["watchlist_count"] == 3

    def test_recent_scans(self):
        c = DashboardController()
        scans = [{"id": i, "status": "completed"} for i in range(15)]
        result = c.scanner_dashboard(recent_scans=scans)
        assert len(result["recent_scans"]) == 10  # capped


class TestOptimizationDashboard:
    def test_default(self):
        c = DashboardController()
        result = c.optimization_dashboard()
        assert result["total_runs"] == 0

    def test_with_runs(self):
        c = DashboardController()
        runs = [
            {"id": 1, "status": "completed", "best_score": 85, "best_params": {"rsi": 14}},
            {"id": 2, "status": "running"},
        ]
        result = c.optimization_dashboard(recent_runs=runs)
        assert result["total_runs"] == 2
        assert len(result["best_parameters"]) == 1

    def test_best_params_sorting(self):
        c = DashboardController()
        runs = [
            {"id": 1, "status": "completed", "best_score": 60, "best_params": {"a": 1}},
            {"id": 2, "status": "completed", "best_score": 95, "best_params": {"a": 2}},
            {"id": 3, "status": "completed", "best_score": 70, "best_params": {"a": 3}},
        ]
        result = c.optimization_dashboard(recent_runs=runs)
        best = result["best_parameters"]
        assert best[0]["score"] == 95
        assert best[1]["score"] == 70

    def test_walk_forward_count(self):
        c = DashboardController()
        wf = [{"id": 1}, {"id": 2}, {"id": 3}]
        mc = [{"id": 4}]
        result = c.optimization_dashboard(walk_forward=wf, monte_carlo=mc)
        assert result["walk_forward_runs"] == 3
        assert result["monte_carlo_runs"] == 1

    def test_top_strategies(self):
        c = DashboardController()
        rankings = [{"name": f"strat_{i}", "score": i * 10} for i in range(15)]
        result = c.optimization_dashboard(rankings=rankings)
        assert len(result["top_strategies"]) == 10


class TestMonitoringDashboard:
    def test_default(self):
        c = DashboardController()
        result = c.monitoring_dashboard()
        assert result["health_checks_passing"] == 0
        assert result["active_alerts"] == 0

    def test_health_checks(self):
        c = DashboardController()
        checks = [
            {"name": "db", "status": "healthy"},
            {"name": "redis", "status": "healthy"},
            {"name": "broker", "status": "unhealthy"},
        ]
        result = c.monitoring_dashboard(health_checks=checks)
        assert result["health_checks_passing"] == 2
        assert result["health_checks_total"] == 3

    def test_active_alerts_filtering(self):
        c = DashboardController()
        alerts = [
            {"id": 1, "status": "active"},
            {"id": 2, "status": "resolved"},
            {"id": 3, "status": "active"},
        ]
        result = c.monitoring_dashboard(alerts=alerts)
        assert result["active_alerts"] == 2

    def test_latency(self):
        c = DashboardController()
        result = c.monitoring_dashboard(latency_ms=12.345)
        assert result["api_latency_ms"] == 12.35

    def test_recent_alerts_capped(self):
        c = DashboardController()
        alerts = [{"id": i, "status": "active"} for i in range(20)]
        result = c.monitoring_dashboard(alerts=alerts)
        assert len(result["recent_alerts"]) == 10


class TestPortfolioDashboard:
    def test_default(self):
        c = DashboardController()
        result = c.portfolio_dashboard()
        assert result["portfolio_count"] == 0
        assert result["account_count"] == 0
        assert result["total_equity"] == 0.0

    def test_with_data(self):
        c = DashboardController()
        portfolios = [{"id": 1, "allocation_method": "equal"}, {"id": 2, "allocation_method": "risk"}]
        accounts = [{"equity": 50000}, {"equity": 75000}]
        result = c.portfolio_dashboard(portfolios=portfolios, accounts=accounts)
        assert result["portfolio_count"] == 2
        assert result["account_count"] == 2
        assert result["total_equity"] == 125000.0

    def test_allocation_methods(self):
        c = DashboardController()
        portfolios = [
            {"allocation_method": "equal"},
            {"allocation_method": "risk"},
            {"allocation_method": "equal"},
        ]
        result = c.portfolio_dashboard(portfolios=portfolios)
        assert sorted(result["allocation_methods"]) == sorted(["equal", "risk"])

    def test_exposure(self):
        c = DashboardController()
        exp = {"long": 60.0, "short": 15.0, "net": 45.0}
        result = c.portfolio_dashboard(exposure=exp)
        assert result["exposure"]["long"] == 60.0

    def test_accounts_capped(self):
        c = DashboardController()
        accounts = [{"equity": i * 1000} for i in range(30)]
        result = c.portfolio_dashboard(accounts=accounts)
        assert len(result["accounts"]) == 20


class TestActivityTimeline:
    def test_empty(self):
        c = DashboardController()
        result = c.activity_timeline()
        assert result == []

    def test_chronological_ordering(self):
        c = DashboardController()
        now = datetime.now(timezone.utc)
        events = [
            {"id": "1", "timestamp": (now - timedelta(hours=2)).isoformat(), "summary": "old"},
            {"id": "2", "timestamp": now.isoformat(), "summary": "new"},
            {"id": "3", "timestamp": (now - timedelta(hours=1)).isoformat(), "summary": "mid"},
        ]
        result = c.activity_timeline(events=events)
        assert result[0]["summary"] == "new"
        assert result[1]["summary"] == "mid"
        assert result[2]["summary"] == "old"

    def test_limit(self):
        c = DashboardController()
        now = datetime.now(timezone.utc)
        events = [{"id": str(i), "timestamp": (now - timedelta(minutes=i)).isoformat()}
                  for i in range(100)]
        result = c.activity_timeline(events=events, limit=20)
        assert len(result) == 20

    def test_default_limit(self):
        c = DashboardController()
        now = datetime.now(timezone.utc)
        events = [{"id": str(i), "timestamp": (now - timedelta(minutes=i)).isoformat()}
                  for i in range(100)]
        result = c.activity_timeline(events=events)
        assert len(result) == 50


class TestSnapshot:
    def test_full_snapshot(self):
        c = DashboardController()
        snap = c.snapshot()
        assert "snapshot_id" in snap
        assert "timestamp" in snap
        assert "system" in snap
        assert "trading" in snap
        assert "scanner" in snap
        assert "optimization" in snap
        assert "monitoring" in snap
        assert "portfolio" in snap
        assert "timeline" in snap

    def test_snapshot_uniqueness(self):
        c = DashboardController()
        snap1 = c.snapshot()
        snap2 = c.snapshot()
        assert snap1["snapshot_id"] != snap2["snapshot_id"]

    def test_snapshot_with_data(self):
        c = DashboardController()
        system = c.system_overview()
        trading = c.trading_overview(daily_pnl=500)
        snap = c.snapshot(system=system, trading=trading)
        assert snap["system"]["overall_status"] == "healthy"
        assert snap["trading"]["daily_pnl"] == 500

    def test_snapshot_determinism(self):
        """Same inputs produce same outputs (except timestamp and snapshot_id)."""
        c1 = DashboardController()
        c2 = DashboardController()
        snap1 = c1.snapshot(
            system=c1.system_overview(),
            trading=c1.trading_overview(daily_pnl=100),
        )
        snap2 = c2.snapshot(
            system=c2.system_overview(),
            trading=c2.trading_overview(daily_pnl=100),
        )
        assert snap1["system"] == snap2["system"]
        assert snap1["trading"] == snap2["trading"]


class TestWidgets:
    def test_build_widgets_full(self):
        c = DashboardController()
        snap = c.snapshot(
            system=c.system_overview(),
            trading=c.trading_overview(),
            scanner=c.scanner_dashboard(),
            optimization=c.optimization_dashboard(),
            monitoring=c.monitoring_dashboard(),
            portfolio=c.portfolio_dashboard(),
            timeline=[{"id": "1", "timestamp": datetime.now(timezone.utc).isoformat()}],
        )
        widgets = c.build_widgets(snap)
        assert len(widgets) == 7  # system, trading, portfolio, monitoring, scanner, optimization, timeline

    def test_widget_data_format(self):
        c = DashboardController()
        snap = c.snapshot(system=c.system_overview())
        widgets = c.build_widgets(snap)
        w = widgets[0]
        d = w.to_dict()
        assert "widget_id" in d
        assert "widget_type" in d
        assert "title" in d
        assert "data" in d
        assert "refresh_interval_s" in d

    def test_partial_widgets(self):
        c = DashboardController()
        snap = c.snapshot(system=c.system_overview())
        widgets = c.build_widgets(snap)
        types = {w.widget_type for w in widgets}
        assert "system" in types
        # Only system was provided, so other widgets shouldn't appear
        assert "trading" not in types


class TestStatistics:
    def test_defaults(self):
        c = DashboardController()
        snap = c.snapshot()
        stats = c.statistics(snap)
        assert stats["total_positions"] == 0
        assert stats["daily_pnl"] == 0.0

    def test_derived_from_snapshot(self):
        c = DashboardController()
        snap = c.snapshot(
            trading=c.trading_overview(daily_pnl=500, positions=[{"symbol": "ES"}, {"symbol": "NQ"}, {"symbol": "CL"}]),
            monitoring=c.monitoring_dashboard(alerts=[{"status": "active"}] * 5),
        )
        stats = c.statistics(snap)
        assert stats["daily_pnl"] == 500
        assert stats["total_positions"] == 3
        assert stats["active_alerts"] == 5


class TestTimelineEvent:
    def test_create(self):
        e = TimelineEvent(event_id="123", event_type="trade", source="live",
                          summary="Buy ES", severity="info")
        d = e.to_dict()
        assert d["event_id"] == "123"
        assert d["event_type"] == "trade"
        assert d["source"] == "live"
        assert d["severity"] == "info"
        assert "timestamp" in d

    def test_default_severity(self):
        e = TimelineEvent(event_id="x", event_type="system", source="monitor",
                          summary="Heartbeat")
        assert e.severity == "info"

    def test_metadata(self):
        e = TimelineEvent(event_id="x", event_type="alert", source="monitor",
                          summary="CPU high", metadata={"cpu": 95})
        assert e.to_dict()["metadata"]["cpu"] == 95


class TestWidgetData:
    def test_create(self):
        w = WidgetData(widget_id="sys", widget_type="system", title="System")
        d = w.to_dict()
        assert d["widget_id"] == "sys"
        assert d["widget_type"] == "system"
        assert d["refresh_interval_s"] == 30

    def test_with_data(self):
        w = WidgetData(widget_id="trade", widget_type="trading", title="Trades",
                       data={"pnl": 100}, refresh_interval_s=5)
        d = w.to_dict()
        assert d["data"]["pnl"] == 100
        assert d["refresh_interval_s"] == 5


class TestLargeDatasets:
    def test_many_timeline_events(self):
        c = DashboardController()
        now = datetime.now(timezone.utc)
        events = [{"id": str(i), "timestamp": (now - timedelta(seconds=i)).isoformat()}
                  for i in range(1000)]
        result = c.activity_timeline(events=events, limit=100)
        assert len(result) == 100
        # Verify ordering
        for i in range(len(result) - 1):
            assert result[i]["timestamp"] >= result[i + 1]["timestamp"]

    def test_many_positions(self):
        c = DashboardController()
        positions = [{"symbol": f"S{i}", "qty": 1} for i in range(500)]
        result = c.trading_overview(positions=positions)
        assert result["open_positions_count"] == 500
        assert len(result["open_positions"]) == 50  # capped

    def test_many_accounts_portfolio(self):
        c = DashboardController()
        accounts = [{"equity": 10000 + i} for i in range(200)]
        result = c.portfolio_dashboard(accounts=accounts)
        assert result["account_count"] == 200
        assert len(result["accounts"]) == 20  # capped

    def test_large_snapshot_serializable(self):
        c = DashboardController()
        snap = c.snapshot(
            system=c.system_overview(
                health_statuses=[{"name": f"s{i}", "status": "healthy"} for i in range(100)]
            ),
            trading=c.trading_overview(
                positions=[{"symbol": f"S{i}"} for i in range(100)]
            ),
        )
        # Must be JSON-serializable
        json.dumps(snap, default=str)


class TestDeterminism:
    def test_system_overview_deterministic(self):
        c1 = DashboardController()
        c2 = DashboardController()
        health = [{"name": "db", "status": "healthy"}]
        assert c1.system_overview(health_statuses=health) == c2.system_overview(health_statuses=health)

    def test_trading_overview_deterministic(self):
        c1 = DashboardController()
        c2 = DashboardController()
        assert c1.trading_overview(daily_pnl=100, positions=[{"symbol": "ES"}]) == \
               c2.trading_overview(daily_pnl=100, positions=[{"symbol": "ES"}])

    def test_scanner_deterministic(self):
        c1 = DashboardController()
        c2 = DashboardController()
        opps = [{"symbol": "ES", "score": 85}, {"symbol": "NQ", "score": 40}]
        assert c1.scanner_dashboard(opportunities=opps) == \
               c2.scanner_dashboard(opportunities=opps)

    def test_optimization_deterministic(self):
        c1 = DashboardController()
        c2 = DashboardController()
        runs = [{"id": 1, "status": "completed", "best_score": 85, "best_params": {}}]
        assert c1.optimization_dashboard(recent_runs=runs) == \
               c2.optimization_dashboard(recent_runs=runs)

    def test_statistics_deterministic(self):
        c1 = DashboardController()
        c2 = DashboardController()
        snap1 = c1.snapshot(trading=c1.trading_overview(daily_pnl=100))
        snap2 = c2.snapshot(trading=c2.trading_overview(daily_pnl=100))
        # Ignore snapshot_id and timestamp
        s1 = c1.statistics(snap1)
        s2 = c2.statistics(snap2)
        assert s1 == s2


class TestSerialization:
    def test_system_overview_serializable(self):
        c = DashboardController()
        result = c.system_overview()
        json.dumps(result, default=str)

    def test_trading_overview_serializable(self):
        c = DashboardController()
        result = c.trading_overview(daily_pnl=100.123)
        json.dumps(result, default=str)

    def test_scanner_serializable(self):
        c = DashboardController()
        result = c.scanner_dashboard(opportunities=[{"symbol": "ES", "score": 80}])
        json.dumps(result, default=str)

    def test_timeline_serializable(self):
        now = datetime.now(timezone.utc)
        events = [{"id": "1", "timestamp": now.isoformat()}]
        c = DashboardController()
        result = c.activity_timeline(events=events)
        json.dumps(result, default=str)

    def test_snapshot_serializable(self):
        c = DashboardController()
        result = c.snapshot()
        json.dumps(result, default=str)

    def test_widgets_serializable(self):
        c = DashboardController()
        snap = c.snapshot(system=c.system_overview())
        widgets = c.build_widgets(snap)
        json.dumps([w.to_dict() for w in widgets], default=str)


class TestEdgeCases:
    def test_none_health_statuses(self):
        c = DashboardController()
        result = c.system_overview(health_statuses=None)
        assert result["overall_status"] == "healthy"

    def test_none_positions(self):
        c = DashboardController()
        result = c.trading_overview(positions=None)
        assert result["open_positions_count"] == 0

    def test_negative_pnl(self):
        c = DashboardController()
        result = c.trading_overview(daily_pnl=-500.123)
        assert result["daily_pnl"] == -500.12

    def test_zero_all(self):
        c = DashboardController()
        result = c.trading_overview(
            daily_pnl=0, portfolio_equity=0, exposure_pct=0
        )
        assert result["daily_pnl"] == 0.0

    def test_mixed_status_unknown(self):
        c = DashboardController()
        health = [{"name": "x", "status": "unknown_status"}]
        result = c.system_overview(health_statuses=health)
        # unknown doesn't increment healthy/degraded/unhealthy but
        # overall should be healthy since none are unhealthy/degraded
        assert result["overall_status"] == "healthy"


class TestPermissions:
    """Dashboard is read-only; all read operations should work."""
    def test_all_reads_no_auth(self):
        c = DashboardController()
        # All methods work without authentication context
        assert c.system_overview()
        assert c.trading_overview()
        assert c.scanner_dashboard()
        assert c.optimization_dashboard()
        assert c.monitoring_dashboard()
        assert c.portfolio_dashboard()
        assert isinstance(c.activity_timeline(), list)
        assert c.snapshot()
        assert c.statistics(c.snapshot())


class TestTimelineEdgeCases:
    def test_mixed_severities(self):
        now = datetime.now(timezone.utc)
        events = [
            {"id": "1", "timestamp": now.isoformat(), "severity": "info"},
            {"id": "2", "timestamp": now.isoformat(), "severity": "critical"},
            {"id": "3", "timestamp": now.isoformat(), "severity": "warning"},
        ]
        c = DashboardController()
        result = c.activity_timeline(events=events)
        assert len(result) == 3

    def test_missing_timestamp(self):
        c = DashboardController()
        events = [{"id": "1", "summary": "test"}, {"id": "2", "summary": "test2"}]
        result = c.activity_timeline(events=events)
        assert len(result) == 2

    def test_single_event(self):
        now = datetime.now(timezone.utc)
        c = DashboardController()
        result = c.activity_timeline(events=[{"id": "x", "timestamp": now.isoformat(), "summary": "solo"}])
        assert len(result) == 1
        assert result[0]["summary"] == "solo"


class TestSnapshotPropagation:
    def test_system_data_flows_to_snapshot(self):
        c = DashboardController()
        system = c.system_overview(
            health_statuses=[{"name": "db", "status": "healthy"}],
            broker_status={"connected": True},
            active_alerts=[{"id": 1}, {"id": 2}],
        )
        snap = c.snapshot(system=system)
        assert snap["system"]["overall_status"] == "healthy"
        assert snap["system"]["broker"]["connected"] is True
        assert snap["system"]["alerts"] == 2

    def test_trading_data_flows_to_snapshot(self):
        c = DashboardController()
        trading = c.trading_overview(
            daily_pnl=1500.0,
            positions=[{"symbol": "ES"}],
            exposure_pct=60.0,
        )
        snap = c.snapshot(trading=trading)
        assert snap["trading"]["daily_pnl"] == 1500.0
        assert snap["trading"]["open_positions_count"] == 1
        assert snap["trading"]["exposure_pct"] == 60.0

    def test_partial_snapshot_usage(self):
        """Snapshot works with only some subsystems."""
        c = DashboardController()
        snap = c.snapshot(system=c.system_overview(), trading=c.trading_overview())
        assert "system" in snap
        assert "trading" in snap
        assert snap["scanner"] == {}
        assert snap["optimization"] == {}


class TestStatisticsCompleteness:
    def test_all_keys_present(self):
        c = DashboardController()
        snap = c.snapshot()
        stats = c.statistics(snap)
        expected_keys = [
            "total_positions", "total_pending_orders", "daily_pnl",
            "unrealized_pnl", "portfolio_equity", "exposure_pct",
            "risk_utilization_pct", "active_alerts", "health_checks_healthy",
            "health_checks_total", "open_opportunities", "portfolio_count",
            "account_count", "total_equity",
        ]
        for key in expected_keys:
            assert key in stats

    def test_statistics_with_real_data(self):
        c = DashboardController()
        trading = c.trading_overview(
            daily_pnl=1234.56, unrealized_pnl=-50.0,
            portfolio_equity=100000, buying_power=200000,
            risk_utilization_pct=15.0, exposure_pct=30.0,
            positions=[{"symbol": "ES"}, {"symbol": "NQ"}],
            orders=[{"status": "pending"}, {"status": "filled"}, {"status": "pending"}],
        )
        portfolio = c.portfolio_dashboard(
            portfolios=[{"allocation_method": "equal"}],
            accounts=[{"equity": 50000}, {"equity": 75000}],
        )
        monitoring = c.monitoring_dashboard(
            health_checks=[{"status": "healthy"}, {"status": "healthy"}, {"status": "degraded"}],
            alerts=[{"status": "active"}] * 4,
        )
        scanner = c.scanner_dashboard(opportunities=[{"score": 80}, {"score": 60}])
        snap = c.snapshot(
            trading=trading, portfolio=portfolio,
            monitoring=monitoring, scanner=scanner,
        )
        stats = c.statistics(snap)
        assert stats["daily_pnl"] == 1234.56
        assert stats["total_positions"] == 2
        assert stats["total_pending_orders"] == 2
        assert stats["account_count"] == 2
        assert stats["total_equity"] == 125000.0
        assert stats["active_alerts"] == 4
        assert stats["health_checks_total"] == 3
        assert stats["health_checks_healthy"] == 2
        assert stats["open_opportunities"] == 2


class TestWidgetVariations:
    def test_custom_refresh_interval(self):
        w = WidgetData(widget_id="test", widget_type="trading",
                       title="Test", refresh_interval_s=10)
        d = w.to_dict()
        assert d["refresh_interval_s"] == 10

    def test_widget_with_complex_data(self):
        w = WidgetData(widget_id="complex", widget_type="portfolio",
                       title="Complex", data={
                           "nested": {"key": [1, 2, 3]},
                           "flags": {"a": True, "b": False},
                       })
        d = w.to_dict()
        assert d["data"]["nested"]["key"] == [1, 2, 3]

    def test_build_widgets_empty_snapshot(self):
        c = DashboardController()
        snap = c.snapshot()
        widgets = c.build_widgets(snap)
        assert len(widgets) == 0  # No sections populated

    def test_build_widgets_timeline_only(self):
        c = DashboardController()
        now = datetime.now(timezone.utc)
        snap = c.snapshot(timeline=[{"id": "1", "timestamp": now.isoformat(), "summary": "x"}])
        widgets = c.build_widgets(snap)
        types = {w.widget_type for w in widgets}
        assert "timeline" in types
        assert len(widgets) == 1


class TestMultipleLayouts:
    def test_timeline_events_from_multiple_sources(self):
        c = DashboardController()
        now = datetime.now(timezone.utc)
        events = []
        for i, source in enumerate(["trade", "alert", "portfolio", "optimization",
                                      "scanner", "broker", "auth", "system"]):
            events.append({
                "id": str(i),
                "source": source,
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
                "summary": f"Event from {source}",
            })
        result = c.activity_timeline(events=events)
        sources = {e["source"] for e in result}
        assert len(sources) == 8

    def test_snapshot_with_timeline(self):
        c = DashboardController()
        now = datetime.now(timezone.utc)
        events = [{"id": str(i), "timestamp": now.isoformat(), "summary": f"e{i}"}
                  for i in range(20)]
        snap = c.snapshot(timeline=c.activity_timeline(events=events))
        assert len(snap["timeline"]) == 20
        widgets = c.build_widgets(snap)
        timeline_widget = [w for w in widgets if w.widget_type == "timeline"]
        assert len(timeline_widget) == 1
        assert len(timeline_widget[0].data["events"]) == 20
