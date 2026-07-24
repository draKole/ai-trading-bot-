"""Monitoring API — health, alerts, audit logs, metrics, dashboard."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.monitoring import (
    MonitoringService, MonitoringController, AlertManager,
)

router = APIRouter()

_controller = MonitoringController()
_alert_manager = AlertManager()


# ─── Health ──────────────────────────────────────────────

@router.get("/health")
async def get_health():
    """Overall health status."""
    return _controller.get_health_summary()


@router.get("/health/system")
async def health_system():
    return _controller.check_system().to_dict()


@router.get("/health/database")
async def health_database(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return _controller.check_database(True).to_dict()
    except Exception:
        return _controller.check_database(False).to_dict()


@router.get("/health/broker")
async def health_broker():
    return _controller.check_broker(False).to_dict()


@router.get("/health/market-data")
async def health_market_data():
    return _controller.check_market_data(True).to_dict()


@router.get("/health/live-trading")
async def health_live_trading():
    return _controller.check_live_trading(False).to_dict()


@router.get("/health/paper-trading")
async def health_paper_trading():
    return _controller.check_paper_trading(0).to_dict()


@router.get("/health/workers")
async def health_workers():
    return _controller.check_workers(True).to_dict()


@router.post("/health/run-all")
async def run_all_checks(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    results = _controller.run_all_checks(db_ok=db_ok)
    service = MonitoringService(db)
    await service.store_health([r.to_dict() for r in results])
    return {"checks": [r.to_dict() for r in results],
            "summary": _controller.get_health_summary()}


# ─── Alerts ──────────────────────────────────────────────

@router.get("/alerts")
async def list_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
):
    return {"alerts": _alert_manager.get_alerts(status=status, severity=severity),
            "summary": _alert_manager.get_summary()}


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
        event_type=event_type, source=source,
        entity_type=entity_type, entity_id=entity_id,
        detail=detail, operator=operator,
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
    service = MonitoringService(db)
    stored = await service.get_metrics(name=name, limit=limit)
    if not stored:
        return {"metrics": _controller.get_metrics(name=name, limit=limit)}
    return {"count": len(stored), "metrics": stored}


@router.post("/metrics")
async def record_metric(
    name: str = Query(...),
    value: float = Query(...),
    tags_json: str = Query("{}"),
    db: AsyncSession = Depends(get_db),
):
    tags = json.loads(tags_json) if tags_json else {}
    _controller.record_metric(name, value, tags)
    service = MonitoringService(db)
    metric_id = await service.store_metric(name, value, tags)
    return {"id": metric_id, "name": name, "value": value}


# ─── Dashboard ───────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard():
    """Dashboard data: health + metrics + alerts summary."""
    return {
        ** _controller.get_dashboard_data(),
        "alerts": _alert_manager.get_summary(),
        "recent_alerts": _alert_manager.get_alerts(status="active")[:5],
    }


# ─── Statistics ──────────────────────────────────────────

@router.get("/statistics")
async def get_statistics(
    db: AsyncSession = Depends(get_db),
):
    service = MonitoringService(db)
    alerts = await service.get_alerts()
    active = sum(1 for a in alerts if a["status"] == "active")
    critical = sum(1 for a in alerts if a["severity"] == "critical" and a["status"] == "active")
    return {
        "total_alerts": len(alerts),
        "active_alerts": active,
        "active_critical": critical,
        "dashboard": _controller.get_dashboard_data(),
    }
