"""Monitoring API — health, alerts, audit logs, metrics, dashboard.

Sprint 1a/b: Real async probes for PostgreSQL, Redis, broker, market data,
workers. Exposes mode, uptime, CPU/memory, active positions, open orders,
and daily signal/trade counts.
"""

from __future__ import annotations

import json
from typing import Optional
from datetime import datetime, timedelta, timezone
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db, check_db_connection
from app.core.redis import check_redis_connection
from app.services.monitoring import (
    MonitoringService, MonitoringController, AlertManager,
)
from app.services.market_data import ProviderRegistry
from app.models.bar import Bar
from app.models.instrument import Instrument

router = APIRouter()


async def _check_market_data_connection() -> dict:
    """Verify provider capability and recent historical bars without fetching data."""
    started = datetime.now(timezone.utc)
    provider_names = ProviderRegistry.list_providers()
    available = []
    for name in provider_names:
        provider = ProviderRegistry.get(name)
        try:
            reachable = await asyncio.wait_for(provider.is_available(), timeout=2.0) if provider is not None else False
        except (TimeoutError, OSError, RuntimeError):
            reachable = False
        if reachable:
            available.append(name)
    provider = available[0] if available else None
    counts: dict[str, int] = {}
    latest = None
    try:
        async with __import__("app.core.database", fromlist=["async_session_factory"]).async_session_factory() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            rows = await session.execute(select(Instrument.symbol, func.count(Bar.id), func.max(Bar.timestamp)).join(Bar, Bar.instrument_id == Instrument.id).where(Instrument.symbol.in_(("ES", "MES", "NQ", "MNQ")), Bar.timestamp >= cutoff).group_by(Instrument.symbol))
            for symbol, count, maximum in rows.all():
                counts[symbol] = int(count)
                if maximum and (latest is None or maximum > latest): latest = maximum
    except Exception:
        counts = {}
    instruments = ("ES", "MES", "NQ", "MNQ")
    present = [s for s in instruments if counts.get(s, 0) > 0]
    # Phase 1 requires all target contracts; partial or empty coverage is degraded.
    ok = bool(provider and present == list(instruments))
    return {"ok": ok, "provider": provider, "provider_status": "available" if provider else "unavailable", "instruments": counts, "complete_instruments": present == list(instruments), "last_successful_update": latest.isoformat() if latest else None, "latency_ms": (datetime.now(timezone.utc)-started).total_seconds()*1000}

_controller = MonitoringController()
_alert_manager = AlertManager()


async def _get_controller() -> MonitoringController:
    """Return the singleton controller, wiring real probes if not already done."""
    if _controller._db_probe is None:
        _controller.register_db_probe(check_db_connection)
    if _controller._redis_probe is None:
        _controller.register_redis_probe(check_redis_connection)
    if _controller._market_data_probe is None:
        _controller.register_market_data_probe(_check_market_data_connection)
    return _controller


# ─── Health ──────────────────────────────────────────────


@router.get("/health")
async def get_health():
    """Overall health status with all components probed."""
    ctrl = await _get_controller()
    await ctrl.run_all_probes()
    return ctrl.get_dashboard_data()


@router.get("/health/system")
async def health_system():
    ctrl = await _get_controller()
    return {
        "system": ctrl.check_system().to_dict(),
        "system_metrics": ctrl.get_system_metrics().to_dict(),
        "mode": ctrl.get_mode_info(),
    }


@router.get("/health/database")
async def health_database():
    ctrl = await _get_controller()
    result = await ctrl.probe_database()
    return result.to_dict()


@router.get("/health/redis")
async def health_redis():
    ctrl = await _get_controller()
    result = await ctrl.probe_redis()
    return result.to_dict()


@router.get("/health/broker")
async def health_broker():
    ctrl = await _get_controller()
    result = await ctrl.probe_broker()
    return result.to_dict()


@router.get("/health/market-data")
async def health_market_data():
    ctrl = await _get_controller()
    result = await ctrl.probe_market_data()
    return result.to_dict()


@router.get("/health/workers")
async def health_workers():
    ctrl = await _get_controller()
    result = await ctrl.probe_workers()
    return result.to_dict()


@router.get("/health/live-trading")
async def health_live_trading():
    ctrl = await _get_controller()
    return ctrl.check_live_trading(False).to_dict()


@router.get("/health/paper-trading")
async def health_paper_trading():
    ctrl = await _get_controller()
    return ctrl.check_paper_trading(0).to_dict()


@router.post("/health/run-all")
async def run_all_checks(db: AsyncSession = Depends(get_db)):
    ctrl = await _get_controller()
    results = await ctrl.run_all_probes()

    service = MonitoringService(db)
    try:
        await service.store_health([r.to_dict() for r in results])
    except Exception:
        pass  # Persistence is best-effort

    return {
        "checks": [r.to_dict() for r in results],
        "summary": ctrl.get_health_summary(),
        "system": ctrl.get_system_metrics().to_dict(),
        "mode": ctrl.get_mode_info(),
        "trading": ctrl.get_trading_status().to_dict(),
    }


# ─── Monitoring Status (Sprint 1b) ──────────────────────


@router.get("/status")
async def get_monitoring_status():
    """Consolidated system status with all fields."""
    ctrl = await _get_controller()
    await ctrl.run_all_probes()
    return ctrl.get_dashboard_data()


# ─── Alerts ──────────────────────────────────────────────


@router.get("/alerts")
async def list_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
):
    return {
        "alerts": _alert_manager.get_alerts(status=status, severity=severity),
        "summary": _alert_manager.get_summary(),
    }


@router.post("/alerts/create")
async def create_alert(
    alert_type: str = Query(...),
    message: str = Query(...),
    severity: str = Query("warning"),
    db: AsyncSession = Depends(get_db),
):
    alert = _alert_manager.create_alert(alert_type, message, severity)
    service = MonitoringService(db)
    await service.store_alert(alert.to_dict())
    return alert.to_dict()


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    alert = _alert_manager.acknowledge_alert(alert_id)
    if alert is None:
        raise HTTPException(404, f"Alert not found: {alert_id}")
    return alert.to_dict()


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    alert = _alert_manager.resolve_alert(alert_id)
    if alert is None:
        raise HTTPException(404, f"Alert not found: {alert_id}")
    return alert.to_dict()


# ─── Audit Logs ──────────────────────────────────────────


@router.get("/audit-logs")
async def get_audit_logs(
    event_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
):
    service = MonitoringService(db)
    logs = await service.get_audit_logs(event_type=event_type, source=source, limit=limit)
    return {"count": len(logs), "logs": logs}


@router.post("/audit-logs")
async def create_audit_log(
    event_type: str = Query(...),
    source: str = Query(...),
    entity_type: str = Query(""),
    entity_id: str = Query(""),
    detail_json: str = Query("{}"),
    operator: str = Query("system"),
    db: AsyncSession = Depends(get_db),
):
    service = MonitoringService(db)
    detail = json.loads(detail_json) if detail_json else {}
    log_id = await service.store_audit_log(
        event_type=event_type,
        source=source,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
        operator=operator,
    )
    return {"id": log_id, "status": "created"}


# ─── Metrics ─────────────────────────────────────────────


@router.get("/metrics")
async def get_metrics(
    name: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get stored metrics or in-memory metrics."""
    ctrl = await _get_controller()
    service = MonitoringService(db)
    stored = await service.get_metrics(name=name, limit=limit)
    if not stored:
        return {"metrics": ctrl.get_metrics(name=name, limit=limit)}
    return {"count": len(stored), "metrics": stored}


@router.post("/metrics")
async def record_metric(
    name: str = Query(...),
    value: float = Query(...),
    tags_json: str = Query("{}"),
    db: AsyncSession = Depends(get_db),
):
    ctrl = await _get_controller()
    tags = json.loads(tags_json) if tags_json else {}
    ctrl.record_metric(name, value, tags)
    service = MonitoringService(db)
    metric_id = await service.store_metric(name, value, tags)
    return {"id": metric_id, "name": name, "value": value}


# ─── Dashboard ───────────────────────────────────────────


@router.get("/dashboard")
async def get_dashboard():
    """Dashboard data: health + metrics + alerts summary."""
    ctrl = await _get_controller()
    return {
        **ctrl.get_dashboard_data(),
        "alerts": _alert_manager.get_summary(),
        "recent_alerts": _alert_manager.get_alerts(status="active")[:5],
    }


# ─── Statistics ──────────────────────────────────────────


@router.get("/statistics")
async def get_statistics(
    db: AsyncSession = Depends(get_db),
):
    ctrl = await _get_controller()
    service = MonitoringService(db)
    alerts = await service.get_alerts()
    active = sum(1 for a in alerts if a["status"] == "active")
    critical = sum(1 for a in alerts if a["severity"] == "critical" and a["status"] == "active")
    return {
        "total_alerts": len(alerts),
        "active_alerts": active,
        "active_critical": critical,
        "dashboard": ctrl.get_dashboard_data(),
    }
