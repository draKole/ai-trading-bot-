"""Operator Dashboard Engine — read-only aggregation of platform state."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class TimelineEvent:
    event_id: str
    event_type: str
    source: str
    summary: str
    severity: str = "info"
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "summary": self.summary,
            "severity": self.severity,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class WidgetData:
    widget_id: str
    widget_type: str
    title: str
    data: dict = field(default_factory=dict)
    refresh_interval_s: int = 30

    def to_dict(self) -> dict:
        return {
            "widget_id": self.widget_id,
            "widget_type": self.widget_type,
            "title": self.title,
            "data": self.data,
            "refresh_interval_s": self.refresh_interval_s,
        }


class DashboardController:
    """Read-only aggregation of platform subsystems for operator visibility."""

    def system_overview(self, health_statuses: list[dict] | None = None,
                        broker_status: dict | None = None,
                        active_alerts: list[dict] | None = None,
                        uptime_seconds: float = 0.0,
                        version: str = "0.0.0",
                        environment: str = "production",
                        session_status: str = "active") -> dict:
        """Aggregate system health, broker, alerts, uptime, version into one view."""
        health_counts = {"healthy": 0, "degraded": 0, "unhealthy": 0}
        if health_statuses:
            for h in health_statuses:
                status = h.get("status", "unhealthy")
                health_counts[status] = health_counts.get(status, 0) + 1

        overall = "healthy"
        if health_counts["unhealthy"] > 0:
            overall = "unhealthy"
        elif health_counts["degraded"] > 0:
            overall = "degraded"

        return {
            "overall_status": overall,
            "health": {
                "counts": health_counts,
                "details": health_statuses or [],
            },
            "broker": broker_status or {"connected": False, "accounts": 0},
            "alerts": len(active_alerts or []),
            "uptime_seconds": round(uptime_seconds, 1),
            "version": version,
            "environment": environment,
            "session": session_status,
        }

    def trading_overview(self, positions: list[dict] | None = None,
                         orders: list[dict] | None = None,
                         daily_pnl: float = 0.0,
                         unrealized_pnl: float = 0.0,
                         portfolio_equity: float = 0.0,
                         buying_power: float = 0.0,
                         risk_utilization_pct: float = 0.0,
                         exposure_pct: float = 0.0) -> dict:
        """Aggregate open positions, orders, P&L, risk/exposure."""
        open_positions = positions or []
        pending_orders = [o for o in (orders or []) if o.get("status") == "pending"]
        filled_orders = [o for o in (orders or []) if o.get("status") == "filled"]

        return {
            "open_positions_count": len(open_positions),
            "open_positions": open_positions[:50],
            "pending_orders_count": len(pending_orders),
            "pending_orders": pending_orders[:50],
            "filled_orders_today": len(filled_orders),
            "daily_pnl": round(daily_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "portfolio_equity": round(portfolio_equity, 2),
            "buying_power": round(buying_power, 2),
            "risk_utilization_pct": round(risk_utilization_pct, 2),
            "exposure_pct": round(exposure_pct, 2),
        }

    def scanner_dashboard(self, opportunities: list[dict] | None = None,
                          watchlists: list[dict] | None = None,
                          recent_scans: list[dict] | None = None) -> dict:
        """Aggregate scanner state — opportunities, watchlists, scan activity."""
        opps = opportunities or []
        scans = recent_scans or []
        wls = watchlists or []

        return {
            "active_opportunities": len(opps),
            "top_opportunities": sorted(opps, key=lambda o: o.get("score", 0), reverse=True)[:10],
            "watchlist_count": len(wls),
            "recent_scans": scans[:10],
            "avg_confidence": round(
                sum(o.get("score", 0) for o in opps) / max(len(opps), 1), 2
            ),
        }

    def optimization_dashboard(self, recent_runs: list[dict] | None = None,
                               walk_forward: list[dict] | None = None,
                               monte_carlo: list[dict] | None = None,
                               rankings: list[dict] | None = None) -> dict:
        """Aggregate optimization state."""
        runs = recent_runs or []
        return {
            "total_runs": len(runs),
            "recent_runs": runs[:10],
            "walk_forward_runs": len(walk_forward or []),
            "monte_carlo_runs": len(monte_carlo or []),
            "top_strategies": (rankings or [])[:10],
            "best_parameters": self._extract_best_params(runs),
        }

    def monitoring_dashboard(self, health_checks: list[dict] | None = None,
                             alerts: list[dict] | None = None,
                             metrics: list[dict] | None = None,
                             latency_ms: float = 0.0) -> dict:
        """Aggregate monitoring state."""
        checks = health_checks or []
        alert_list = alerts or []
        active_alerts = [a for a in alert_list if a.get("status") == "active"]

        return {
            "health_checks_passing": sum(1 for c in checks if c.get("status") == "healthy"),
            "health_checks_total": len(checks),
            "active_alerts": len(active_alerts),
            "recent_alerts": alert_list[:10],
            "api_latency_ms": round(latency_ms, 2),
            "metrics": (metrics or [])[:10],
        }

    def portfolio_dashboard(self, portfolios: list[dict] | None = None,
                            accounts: list[dict] | None = None,
                            statistics: list[dict] | None = None,
                            exposure: dict | None = None) -> dict:
        """Aggregate portfolio state."""
        pf = portfolios or []
        accts = accounts or []
        return {
            "portfolio_count": len(pf),
            "account_count": len(accts),
            "total_equity": round(sum(a.get("equity", 0) for a in accts), 2),
            "allocation_methods": list(set(p.get("allocation_method", "equal") for p in pf)),
            "exposure": exposure or {},
            "statistics": (statistics or [])[:10],
            "accounts": accts[:20],
        }

    def activity_timeline(self, events: list[dict] | None = None,
                          limit: int = 50) -> list[dict]:
        """Build unified chronological timeline from heterogeneous events."""
        timeline_events = events or []
        sorted_events = sorted(timeline_events,
                               key=lambda e: e.get("timestamp", "1970-01-01T00:00:00"),
                               reverse=True)
        return sorted_events[:limit]

    def snapshot(self, system: dict | None = None, trading: dict | None = None,
                 scanner: dict | None = None, optimization: dict | None = None,
                 monitoring: dict | None = None, portfolio: dict | None = None,
                 timeline: list[dict] | None = None) -> dict:
        """Capture full platform state at this moment."""
        return {
            "snapshot_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": system or {},
            "trading": trading or {},
            "scanner": scanner or {},
            "optimization": optimization or {},
            "monitoring": monitoring or {},
            "portfolio": portfolio or {},
            "timeline": timeline or [],
        }

    def build_widgets(self, snapshot: dict) -> list[WidgetData]:
        """Generate default widget set from a snapshot."""
        widgets = []
        if snapshot.get("system"):
            widgets.append(WidgetData(
                widget_id="system-overview",
                widget_type="system",
                title="System Overview",
                data=snapshot["system"],
            ))
        if snapshot.get("trading"):
            widgets.append(WidgetData(
                widget_id="trading-overview",
                widget_type="trading",
                title="Trading Overview",
                data=snapshot["trading"],
            ))
        if snapshot.get("portfolio"):
            widgets.append(WidgetData(
                widget_id="portfolio-summary",
                widget_type="portfolio",
                title="Portfolio Summary",
                data=snapshot["portfolio"],
            ))
        if snapshot.get("monitoring"):
            widgets.append(WidgetData(
                widget_id="monitoring-status",
                widget_type="monitoring",
                title="System Health",
                data=snapshot["monitoring"],
            ))
        if snapshot.get("scanner"):
            widgets.append(WidgetData(
                widget_id="scanner-opportunities",
                widget_type="scanner",
                title="Scanner Opportunities",
                data=snapshot["scanner"],
            ))
        if snapshot.get("optimization"):
            widgets.append(WidgetData(
                widget_id="optimization-status",
                widget_type="optimization",
                title="Optimization Status",
                data=snapshot["optimization"],
            ))
        if snapshot.get("timeline"):
            widgets.append(WidgetData(
                widget_id="activity-timeline",
                widget_type="timeline",
                title="Activity Timeline",
                data={"events": snapshot["timeline"][:20]},
            ))
        return widgets

    def statistics(self, snapshot: dict) -> dict:
        """Derive dashboard-level aggregate statistics from full snapshot."""
        trading = snapshot.get("trading", {})
        portfolio = snapshot.get("portfolio", {})
        monitoring = snapshot.get("monitoring", {})
        scanner = snapshot.get("scanner", {})

        return {
            "total_positions": trading.get("open_positions_count", 0),
            "total_pending_orders": trading.get("pending_orders_count", 0),
            "daily_pnl": trading.get("daily_pnl", 0.0),
            "unrealized_pnl": trading.get("unrealized_pnl", 0.0),
            "portfolio_equity": trading.get("portfolio_equity", 0.0),
            "exposure_pct": trading.get("exposure_pct", 0.0),
            "risk_utilization_pct": trading.get("risk_utilization_pct", 0.0),
            "active_alerts": monitoring.get("active_alerts", 0),
            "health_checks_healthy": monitoring.get("health_checks_passing", 0),
            "health_checks_total": monitoring.get("health_checks_total", 0),
            "open_opportunities": scanner.get("active_opportunities", 0),
            "portfolio_count": portfolio.get("portfolio_count", 0),
            "account_count": portfolio.get("account_count", 0),
            "total_equity": portfolio.get("total_equity", 0.0),
        }

    def _extract_best_params(self, runs: list[dict]) -> list[dict]:
        """Extract best parameter sets from runs."""
        best = []
        for r in runs:
            if r.get("status") == "completed" and r.get("best_score"):
                best.append({
                    "run_id": r.get("id"),
                    "score": r.get("best_score"),
                    "params": r.get("best_params", {}),
                })
        return sorted(best, key=lambda b: b.get("score", 0), reverse=True)[:5]
