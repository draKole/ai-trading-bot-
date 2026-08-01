"""Health check endpoints.

Provides basic liveness check at /health and a comprehensive
/full endpoint backed by the production MonitoringController.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic liveness check — minimal overhead, always returns 200 if the API is up."""
    return {"status": "ok"}


@router.get("/health/full")
async def health_full():
    """Comprehensive health check backed by the production HealthChecker.

    Runs all async probes (database, Redis, broker, market data, workers),
    collects system metrics, and returns a deterministic response with
    overall status, per-component results, and readiness semantics.

    Response schema:
        overall:       healthy | degraded | unhealthy
        components:    {component: {status, detail, latency_ms}}
        system:        {cpu_percent, memory_percent, memory_used_mb, ...}
        mode:          {mode, live_allowed, uptime_seconds}
        trading:       {active_positions, open_orders, signals_today, trades_today}
        timestamp:     ISO 8601 UTC
    """
    from app.core.database import check_db_connection
    from app.core.redis import check_redis_connection
    from app.services.monitoring import MonitoringController
    from app.api.monitoring import _check_market_data_connection

    ctrl = MonitoringController()

    # Wire real probes (same pattern as monitoring API)
    ctrl.register_db_probe(check_db_connection)
    ctrl.register_redis_probe(check_redis_connection)
    ctrl.register_market_data_probe(_check_market_data_connection)

    # Run all probes
    results = await ctrl.run_all_probes()

    # Build response
    components: dict[str, dict] = {}
    worst_status = "healthy"
    for r in results:
        components[r.component] = r.to_dict()
        if r.status == "unhealthy":
            worst_status = "unhealthy"
        elif r.status == "degraded" and worst_status != "unhealthy":
            worst_status = "degraded"

    system_metrics = ctrl.get_system_metrics()
    mode_info = ctrl.get_mode_info()
    trading = ctrl.get_trading_status()

    return {
        "overall": worst_status,
        "components": components,
        "system": system_metrics.to_dict(),
        "mode": mode_info,
        "trading": trading.to_dict(),
        "timestamp": max(
            (r.timestamp for r in results if r.timestamp),
            default=None,
        ),
    }
