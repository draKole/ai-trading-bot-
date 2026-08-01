"""Monitoring Engine — health checks, metrics, dashboard data.

Read-only: observes system state, never modifies trading decisions.

Sprint 1a: Production-ready with real async probes for PostgreSQL, Redis,
worker heartbeat, broker, market data, API self-check, system metrics
(CPU, memory, uptime), and trading status (positions, orders, daily counts).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from app.core.config import settings


# ── Dataclasses ──────────────────────────────────────────────


@dataclass
class HealthCheck:
    """Result of a single health check."""

    component: str
    status: str  # healthy, degraded, unhealthy, unknown
    detail: str = ""
    latency_ms: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "status": self.status,
            "detail": self.detail,
            "latency_ms": round(self.latency_ms, 2) if self.latency_ms is not None else None,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class MetricPoint:
    """A single metric data point."""

    name: str
    value: float
    tags: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "tags": self.tags,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SystemMetrics:
    """Current system resource metrics."""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_percent": round(self.memory_percent, 1),
            "memory_used_mb": round(self.memory_used_mb, 1),
            "memory_total_mb": round(self.memory_total_mb, 1),
            "uptime_seconds": round(self.uptime_seconds, 0),
            "uptime_human": self._format_uptime(self.uptime_seconds),
        }

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        elif seconds < 86400:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            return f"{h}h {m}m"
        else:
            d = int(seconds // 86400)
            h = int((seconds % 86400) // 3600)
            return f"{d}d {h}h"


@dataclass
class TradingStatus:
    """Current trading activity snapshot."""

    active_positions: int = 0
    open_orders: int = 0
    signals_today: int = 0
    trades_today: int = 0

    def to_dict(self) -> dict:
        return {
            "active_positions": self.active_positions,
            "open_orders": self.open_orders,
            "signals_today": self.signals_today,
            "trades_today": self.trades_today,
        }


# ── MonitoringController ────────────────────────────────────


class MonitoringController:
    """Read-only observability controller.

    Performs real async health checks against PostgreSQL, Redis, broker,
    market data, and worker heartbeats. Collects system metrics and
    tracks trading status. Never modifies trading state.
    """

    def __init__(self) -> None:
        self._health_history: list[HealthCheck] = []
        self._metrics: list[MetricPoint] = []
        self._start_time: float = time.monotonic()
        self._mode: str = settings.TRADING_MODE
        self._trading_status = TradingStatus()

        # Probes — injected by the application at startup
        self._db_probe: Callable[[], Awaitable[bool]] | None = None
        self._redis_probe: Callable[[], Awaitable[bool]] | None = None
        self._broker_probe: Callable[[], Awaitable[bool]] | None = None
        self._market_data_probe: Callable[[], Awaitable[bool]] | None = None
        self._worker_heartbeat_probe: Callable[[], Awaitable[bool]] | None = None
        self._position_counter: Callable[[], Awaitable[int]] | None = None
        self._order_counter: Callable[[], Awaitable[int]] | None = None
        self._signal_counter: Callable[[], Awaitable[int]] | None = None
        self._trade_counter: Callable[[], Awaitable[int]] | None = None

    # ── Probe Registration ──────────────────────────────────

    def register_db_probe(self, probe: Callable[[], Awaitable[bool]]) -> None:
        self._db_probe = probe

    def register_redis_probe(self, probe: Callable[[], Awaitable[bool]]) -> None:
        self._redis_probe = probe

    def register_broker_probe(self, probe: Callable[[], Awaitable[bool]]) -> None:
        self._broker_probe = probe

    def register_market_data_probe(self, probe: Callable[[], Awaitable[bool]]) -> None:
        self._market_data_probe = probe

    def register_worker_heartbeat_probe(self, probe: Callable[[], Awaitable[bool]]) -> None:
        self._worker_heartbeat_probe = probe

    # ── Trading Status Registration ─────────────────────────

    def register_position_counter(self, counter: Callable[[], Awaitable[int]]) -> None:
        self._position_counter = counter

    def register_order_counter(self, counter: Callable[[], Awaitable[int]]) -> None:
        self._order_counter = counter

    def register_signal_counter(self, counter: Callable[[], Awaitable[int]]) -> None:
        self._signal_counter = counter

    def register_trade_counter(self, counter: Callable[[], Awaitable[int]]) -> None:
        self._trade_counter = counter

    # ── Health Checks (sync — for backward compat / quick calls) ──

    def check_system(self) -> HealthCheck:
        """System-level health check (always healthy if running)."""
        return HealthCheck(
            component="system",
            status="healthy",
            detail="System operational",
        )

    def check_api(self) -> HealthCheck:
        """API self-check."""
        return HealthCheck(
            component="api",
            status="healthy",
            detail="API responding",
        )

    def check_database(self, db_available: bool = True) -> HealthCheck:
        return HealthCheck(
            component="database",
            status="healthy" if db_available else "unhealthy",
            detail="Connected" if db_available else "Database unavailable",
        )

    def check_redis(self, redis_available: bool = False) -> HealthCheck:
        return HealthCheck(
            component="redis",
            status="healthy" if redis_available else "degraded",
            detail="Connected" if redis_available else "Redis unavailable",
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

    # ── Async Health Probes (Sprint 1a — production) ────────

    async def probe_database(self) -> HealthCheck:
        """Probe PostgreSQL connectivity."""
        t0 = time.monotonic()
        if self._db_probe:
            try:
                ok = await self._db_probe()
            except Exception as exc:
                ok = False
                detail = f"Database probe error: {exc}"
            else:
                detail = "Connected" if ok else "Database unavailable"
        else:
            ok = False
            detail = "No database probe registered"
        latency = (time.monotonic() - t0) * 1000
        return HealthCheck(
            component="database",
            status="healthy" if ok else "unhealthy",
            detail=detail,
            latency_ms=latency,
        )

    async def probe_redis(self) -> HealthCheck:
        """Probe Redis connectivity."""
        t0 = time.monotonic()
        if self._redis_probe:
            try:
                ok = await self._redis_probe()
            except Exception as exc:
                ok = False
                detail = f"Redis probe error: {exc}"
            else:
                detail = "Connected" if ok else "Redis unavailable"
        else:
            ok = False
            detail = "No Redis probe registered"
        latency = (time.monotonic() - t0) * 1000
        return HealthCheck(
            component="redis",
            status="healthy" if ok else "degraded",
            detail=detail,
            latency_ms=latency,
        )

    async def probe_broker(self) -> HealthCheck:
        """Probe broker connection."""
        t0 = time.monotonic()
        if self._broker_probe:
            try:
                ok = await self._broker_probe()
            except Exception as exc:
                ok = False
                detail = f"Broker probe error: {exc}"
            else:
                detail = "Connected" if ok else "Broker disconnected"
        else:
            ok = False
            detail = "No broker probe registered"
        latency = (time.monotonic() - t0) * 1000
        return HealthCheck(
            component="broker",
            status="healthy" if ok else "degraded",
            detail=detail,
            latency_ms=latency,
        )

    async def probe_market_data(self) -> HealthCheck:
        """Probe market data feed."""
        t0 = time.monotonic()
        metadata: dict[str, Any] = {}
        if self._market_data_probe:
            try:
                probe_result = await self._market_data_probe()
                metadata = probe_result if isinstance(probe_result, dict) else {}
                ok = bool(metadata.get("ok", probe_result))
            except Exception as exc:
                ok = False
                detail = f"Market data probe error: {exc}"
            else:
                detail = "Data flowing" if ok else "Market data stalled"
        else:
            ok = False
            detail = "No market data probe registered"
        latency = (time.monotonic() - t0) * 1000
        return HealthCheck(
            component="market_data",
            status="healthy" if ok else "degraded",
            detail=detail,
            latency_ms=latency,
            metadata=metadata,
        )

    async def probe_workers(self) -> HealthCheck:
        """Probe worker heartbeat."""
        t0 = time.monotonic()
        if self._worker_heartbeat_probe:
            try:
                ok = await self._worker_heartbeat_probe()
            except Exception as exc:
                ok = False
                detail = f"Worker probe error: {exc}"
            else:
                detail = "Workers running" if ok else "Workers unresponsive"
        else:
            ok = False
            detail = "No worker probe registered"
        latency = (time.monotonic() - t0) * 1000
        return HealthCheck(
            component="workers",
            status="healthy" if ok else "degraded",
            detail=detail,
            latency_ms=latency,
        )

    # ── Run All Probes ──────────────────────────────────────

    def run_all_checks(
        self,
        db_ok: bool = True,
        broker_ok: bool = False,
        market_ok: bool = True,
        live_sessions: int = 0,
        paper_sessions: int = 0,
    ) -> list[HealthCheck]:
        """Run all synchronous health checks and return results."""
        results = [
            self.check_system(),
            self.check_api(),
            self.check_database(db_ok),
            self.check_redis(False),
            self.check_broker(broker_ok),
            self.check_market_data(market_ok),
            self.check_live_trading(live_sessions > 0),
            self.check_paper_trading(paper_sessions),
            self.check_workers(),
        ]
        self._health_history.extend(results)
        return results

    async def run_all_probes(self) -> list[HealthCheck]:
        """Run all async production probes and return results."""
        results = [
            self.check_system(),
            self.check_api(),
            await self.probe_database(),
            await self.probe_redis(),
            await self.probe_broker(),
            await self.probe_market_data(),
            await self.probe_workers(),
        ]
        self._health_history.extend(results)
        await self._refresh_trading_status()
        return results

    # ── Health Summary ──────────────────────────────────────

    def get_health_summary(self) -> dict:
        """Return a summary of current health status."""
        if not self._health_history:
            return {"overall": "unknown", "components": {}}
        latest = {}
        seen: set[str] = set()
        for h in reversed(self._health_history):
            if h.component not in seen:
                latest[h.component] = {"status": h.status, "detail": h.detail}
                seen.add(h.component)
        unhealthy = [c for c in latest.values() if c["status"] == "unhealthy"]
        degraded = [c for c in latest.values() if c["status"] == "degraded"]
        if unhealthy:
            overall = "unhealthy"
        elif degraded:
            overall = "degraded"
        else:
            overall = "healthy"
        return {"overall": overall, "components": latest}

    # ── System Metrics ──────────────────────────────────────

    def get_system_metrics(self) -> SystemMetrics:
        """Collect current CPU, memory, and uptime metrics."""
        uptime = time.monotonic() - self._start_time
        cpu = 0.0
        mem_percent = 0.0
        mem_used = 0.0
        mem_total = 0.0

        try:
            import psutil  # type: ignore[import-untyped]
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            mem_percent = mem.percent
            mem_used = mem.used / (1024 * 1024)
            mem_total = mem.total / (1024 * 1024)
        except ImportError:
            # Fallback: use /proc on Linux
            try:
                with open("/proc/loadavg") as f:
                    cpu = float(f.read().split()[0]) * 100.0
            except Exception:
                cpu = 0.0
            try:
                with open("/proc/meminfo") as f:
                    lines = f.readlines()
                mem_total_kb = 0
                mem_avail_kb = 0
                for line in lines:
                    if line.startswith("MemTotal:"):
                        mem_total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail_kb = int(line.split()[1])
                if mem_total_kb > 0:
                    mem_used = (mem_total_kb - mem_avail_kb) / 1024.0
                    mem_total = mem_total_kb / 1024.0
                    mem_percent = (mem_used / mem_total) * 100.0
            except Exception:
                pass

        return SystemMetrics(
            cpu_percent=round(cpu, 1),
            memory_percent=round(mem_percent, 1),
            memory_used_mb=round(mem_used, 1),
            memory_total_mb=round(mem_total, 1),
            uptime_seconds=uptime,
        )

    @property
    def mode(self) -> str:
        return self._mode

    def get_mode_info(self) -> dict:
        return {
            "mode": self._mode,
            "live_allowed": settings.LIVE_ALLOWED,
            "uptime_seconds": round(time.monotonic() - self._start_time, 0),
        }

    # ── Trading Status ──────────────────────────────────────

    def get_trading_status(self) -> TradingStatus:
        """Return a copy of current trading status."""
        return TradingStatus(
            active_positions=self._trading_status.active_positions,
            open_orders=self._trading_status.open_orders,
            signals_today=self._trading_status.signals_today,
            trades_today=self._trading_status.trades_today,
        )

    def update_trading_status(
        self,
        active_positions: int | None = None,
        open_orders: int | None = None,
        signals_today: int | None = None,
        trades_today: int | None = None,
    ) -> None:
        """Update trading status fields. Only provided fields are changed."""
        if active_positions is not None:
            self._trading_status.active_positions = active_positions
        if open_orders is not None:
            self._trading_status.open_orders = open_orders
        if signals_today is not None:
            self._trading_status.signals_today = signals_today
        if trades_today is not None:
            self._trading_status.trades_today = trades_today

    async def _refresh_trading_status(self) -> None:
        """Refresh trading status from registered counters."""
        if self._position_counter:
            try:
                self._trading_status.active_positions = await self._position_counter()
            except Exception:
                pass
        if self._order_counter:
            try:
                self._trading_status.open_orders = await self._order_counter()
            except Exception:
                pass
        if self._signal_counter:
            try:
                self._trading_status.signals_today = await self._signal_counter()
            except Exception:
                pass
        if self._trade_counter:
            try:
                self._trading_status.trades_today = await self._trade_counter()
            except Exception:
                pass

    # ── Metrics ─────────────────────────────────────────────

    def record_metric(self, name: str, value: float, tags: dict | None = None) -> MetricPoint:
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
        result: dict[str, dict[str, float | int]] = {}
        for name, values in by_name.items():
            result[name] = {
                "latest": values[-1],
                "avg": round(sum(values) / len(values), 2),
                "min": min(values),
                "max": max(values),
                "count": len(values),
            }
        return result

    # ── Dashboard Data ──────────────────────────────────────

    def get_dashboard_data(self) -> dict:
        """Get combined dashboard data (health + metrics + system + trading summary)."""
        return {
            "health": self.get_health_summary(),
            "metrics": self.get_aggregated_metrics(),
            "system": self.get_system_metrics().to_dict(),
            "mode": self.get_mode_info(),
            "trading": self.get_trading_status().to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
