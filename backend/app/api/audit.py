"""Audit Log API — query immutable event history."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.audit import AuditLogService

router = APIRouter()


@router.get("/audit")
async def query_audit_logs(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    client_order_id: Optional[str] = Query(None, description="Filter by client order ID"),
    instrument: Optional[str] = Query(None, description="Filter by instrument"),
    mode: Optional[str] = Query(None, description="Filter by trading mode (paper/live)"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Query audit log entries with optional filters. Returns paginated results."""
    service = AuditLogService(db)
    entries, total = await service.query_logs(
        event_type=event_type,
        client_order_id=client_order_id,
        instrument=instrument,
        mode=mode,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": entries,
    }
