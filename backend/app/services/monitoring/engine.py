"""Monitoring Engine — health checks, metrics, dashboard data.

Read-only: observes system state, never modifies trading decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class HealthCheck:
    """Result of a single health check."""
    component: str
    status: str  # healthy, degraded, unhealthy, unknown
    detail: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "component": self.component, "status": self.status,
            "detail": self.detail, "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    tags: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "name": self.name, "value": self.value,
            "tags": self.tags, "timestamp": self.timestamp.isoformat(),
        }


class MonitoringController:
    """Read-only observability controller.

    Performs health checks, collects metrics, and provides
    dashboard-ready data. Never modifies trading state.
    """

    def __init__(self):
        self._health_history: list[HealthCheck] = []
        self._metrics: list[MetricPoint] = []

    # ── Health Checks ────────────────────────────────────

    def check_system(self) -> HealthCheck:
        """System-level health check (always healthy if running)."""
        return HealthCheck(component="system", status="healthy",
                          detail="System operational")

    def check_database(self, db_available: bool = True) -> HealthCheck:
        return HealthCheck(
            component="database",
            status="healthy" if db_available else "unhealthy",
            detail="Connected" if db_available else "Database unavailable",
        )

    def check_broker(self, connected: bool = False) -> HealthCheck:
        return HealthCheck(
            component="broker",
            status="healthy" if connected else "degraded",
            detail="Connected" if connected else "Broker disconnected",
        )

    def check_market_data(self, flowing: bool = True) -> HealthCheck:
        return HealthCheck(
            component="market_data",
            status="healthy" if flowing else "degraded",
            detail="Data flowing" if flowing else "Market data stalled",
        )

    def check_live_trading(self, sessions_active: bool = False) -> HealthCheck:
        return HealthCheck(
            component="live_trading",
            status="healthy" if sessions_active else "degraded",
            detail=f"{'Sessions active' if sessions_active else 'No active sessions'}",
        )

    def check_paper_trading(self, sessions: int = 0) -> HealthCheck:
        return HealthCheck(
            component="paper_trading",
            status="healthy",
            detail=f"{sessions} paper sessions",
        )

    def check_workers(self, running: bool = True) -> HealthCheck:
        return HealthCheck(
            component="workers",
            status="healthy" if running else "degraded",
            detail="Running" if running else "Workers stopped",
        )

    def run_all_checks(self, db_ok: bool = True, broker_ok: bool = False,
                       market_ok: bool = True, live_sessions: int = 0,
                       paper_sessions: int = 0) -> list[HealthCheck]:
        """Run all health checks and return results."""
        results = [
            self.check_system(),
            self.check_database(db_ok),
            self.check_broker(broker_ok),
            self.check_market_data(market_ok),
            self.check_live_trading(live_sessions > 0),
            self.check_paper_trading(paper_sessions),
            self.check_workers(),
        ]
        self._health_history.extend(results)
        return results

    def get_health_summary(self) -> dict:
        """Return a summary of current health status."""
        if not self._health_history:
            return {"overall": "unknown", "components": {}}
        latest = {}
        for h in self._health_history[-7:]:
            latest[h.component] = {"status": h.status, "detail": h.detail}
        unhealthy = [c for c in latest.values() if c["status"] == "unhealthy"]
        degraded = [c for c in latest.values() if c["status"] == "degraded"]
        if unhealthy:
            overall = "unhealthy"
        elif degraded:
            overall = "degraded"
        else:
            overall = "healthy"
        return {"overall": overall, "components": latest}

    # ── Metrics ──────────────────────────────────────────

    def record_metric(self, name: str, value: float, tags: dict | None = None):
        """Record a metric value."""
        point = MetricPoint(name=name, value=value, tags=tags or {})
        self._metrics.append(point)
        return point

    def get_metrics(self, name: str | None = None, limit: int = 100) -> list[dict]:
        """Get recorded metrics, optionally filtered by name."""
        metrics = self._metrics
        if name:
            metrics = [m for m in metrics if m.name == name]
        return [m.to_dict() for m in metrics[-limit:]]

    def get_aggregated_metrics(self) -> dict:
        """Get aggregated summary of recent metrics."""
        if not self._metrics:
            return {}
        by_name: dict[str, list[float]] = {}
        for m in self._metrics:
            by_name.setdefault(m.name, []).append(m.value)
        result = {}
        for name, values in by_name.items():
            result[name] = {
                "latest": values[-1],
                "avg": round(sum(values) / len(values), 2),
                "min": min(values),
                "max": max(values),
                "count": len(values),
            }
        return result

    # ── Dashboard Data ───────────────────────────────────

    def get_dashboard_data(self) -> dict:
        """Get combined dashboard data (health + metrics summary)."""
        return {
            "health": self.get_health_summary(),
            "metrics": self.get_aggregated_metrics(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
