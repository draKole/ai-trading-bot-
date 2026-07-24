"""Monitoring Service — persistence for health, alerts, audit, and metrics."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_, desc, func

from app.models.monitoring import (
    SystemHealth, Alert as AlertModel, AuditLog as AuditModel,
    PerformanceMetric as MetricModel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class MonitoringService:
    """Persistence service for monitoring data."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def store_health(self, checks: list[dict]) -> int:
        count = 0
        for c in checks:
            self.session.add(SystemHealth(
                component=c["component"], status=c["status"],
                detail=c.get("detail", ""),
            ))
            count += 1
        await self.session.flush()
        return count

    async def get_health(self, component: str | None = None,
                         limit: int = 50) -> list[dict]:
        conditions = []
        if component:
            conditions.append(SystemHealth.component == component)
        query = select(SystemHealth).order_by(desc(SystemHealth.timestamp)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return [
            {"id": h.id, "component": h.component, "status": h.status,
             "detail": h.detail, "timestamp": h.timestamp.isoformat() if h.timestamp else None}
            for h in result.scalars().all()
        ]

    async def store_alert(self, alert: dict) -> int:
        db_alert = AlertModel(
            alert_type=alert.get("alert_type", ""),
            severity=alert.get("severity", "warning"),
            message=alert.get("message", ""),
            status=alert.get("status", "active"),
        )
        self.session.add(db_alert)
        await self.session.flush()
        return db_alert.id

    async def update_alert(self, alert_id: int, updates: dict) -> dict | None:
        result = await self.session.execute(
            select(AlertModel).where(AlertModel.id == alert_id)
        )
        a = result.scalar_one_or_none()
        if a is None:
            return None
        for k, v in updates.items():
            if hasattr(a, k):
                setattr(a, k, v)
        await self.session.flush()
        return {"id": a.id, "status": a.status}

    async def get_alerts(self, status: str | None = None,
                         limit: int = 100) -> list[dict]:
        conditions = []
        if status:
            conditions.append(AlertModel.status == status)
        query = select(AlertModel).order_by(desc(AlertModel.created_at)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return [
            {"id": a.id, "alert_type": a.alert_type, "severity": a.severity,
             "message": a.message, "status": a.status,
             "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
             "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in result.scalars().all()
        ]

    async def store_audit_log(self, event_type: str, source: str,
                              entity_type: str = "", entity_id: str = "",
                              detail: dict | None = None,
                              operator: str = "system") -> int:
        import json as _json
        db_log = AuditModel(
            event_type=event_type, source=source,
            entity_type=entity_type, entity_id=entity_id,
            detail_json=_json.dumps(detail or {}),
            operator=operator,
        )
        self.session.add(db_log)
        await self.session.flush()
        return db_log.id

    async def get_audit_logs(self, event_type: str | None = None,
                             source: str | None = None,
                             limit: int = 200) -> list[dict]:
        conditions = []
        if event_type:
            conditions.append(AuditModel.event_type == event_type)
        if source:
            conditions.append(AuditModel.source == source)
        query = select(AuditModel).order_by(desc(AuditModel.timestamp)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return [
            {"id": l.id, "event_type": l.event_type, "source": l.source,
             "entity_type": l.entity_type, "entity_id": l.entity_id,
             "detail_json": l.detail_json, "operator": l.operator,
             "timestamp": l.timestamp.isoformat() if l.timestamp else None}
            for l in result.scalars().all()
        ]

    async def store_metric(self, name: str, value: float,
                           tags: dict | None = None) -> int:
        import json as _json
        db_metric = MetricModel(
            name=name, value=value,
            tags_json=_json.dumps(tags or {}),
        )
        self.session.add(db_metric)
        await self.session.flush()
        return db_metric.id

    async def get_metrics(self, name: str | None = None,
                          limit: int = 100) -> list[dict]:
        conditions = []
        if name:
            conditions.append(MetricModel.name == name)
        query = select(MetricModel).order_by(desc(MetricModel.timestamp)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return [
            {"id": m.id, "name": m.name, "value": m.value,
             "tags_json": m.tags_json,
             "timestamp": m.timestamp.isoformat() if m.timestamp else None}
            for m in result.scalars().all()
        ]
