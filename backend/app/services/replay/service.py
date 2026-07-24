"""Replay Persistence Service — CRUD for replay sessions, snapshots, and events."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_, desc

from app.models.replay import ReplaySession, ReplaySnapshot as SnapshotModel, ReplayEvent as EventModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class ReplayService:
    """Service for replay session, snapshot, and event persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Sessions ───────────────────────────────────────────

    async def create_session(self, config: dict) -> dict:
        """Create a new replay session from config."""
        import json as _json
        db_session = ReplaySession(
            instrument=config["instrument"],
            timeframe=config.get("timeframe", "5m"),
            start_time=config["start_time"],
            end_time=config["end_time"],
            mode=config.get("mode", "candle_by_candle"),
            status="idle",
            bar_count=0,
            bar_index=0,
            config_json=_json.dumps(config, default=str),
        )
        self.session.add(db_session)
        await self.session.flush()
        return {
            "id": db_session.id,
            "instrument": db_session.instrument,
            "timeframe": db_session.timeframe,
            "start_time": db_session.start_time.isoformat() if db_session.start_time else None,
            "end_time": db_session.end_time.isoformat() if db_session.end_time else None,
            "mode": db_session.mode,
            "status": db_session.status,
            "bar_count": db_session.bar_count,
            "bar_index": db_session.bar_index,
        }

    async def update_session(self, session_id: int, updates: dict) -> dict | None:
        """Update a replay session with current state."""
        result = await self.session.execute(
            select(ReplaySession).where(ReplaySession.id == session_id)
        )
        db_session = result.scalar_one_or_none()
        if db_session is None:
            return None

        for key, value in updates.items():
            if hasattr(db_session, key):
                setattr(db_session, key, value)

        db_session.updated_at = datetime.utcnow()
        await self.session.flush()
        return {
            "id": db_session.id,
            "status": db_session.status,
            "bar_index": db_session.bar_index,
            "bar_count": db_session.bar_count,
        }

    async def get_session(self, session_id: int) -> dict | None:
        """Get a replay session by ID."""
        result = await self.session.execute(
            select(ReplaySession).where(ReplaySession.id == session_id)
        )
        db_session = result.scalar_one_or_none()
        if db_session is None:
            return None
        return self._session_to_dict(db_session)

    async def get_sessions(
        self, instrument: str | None = None, status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List replay sessions with optional filters."""
        conditions = []
        if instrument:
            conditions.append(ReplaySession.instrument == instrument.upper())
        if status:
            conditions.append(ReplaySession.status == status)

        query = select(ReplaySession).order_by(desc(ReplaySession.created_at)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return [self._session_to_dict(s) for s in result.scalars().all()]

    def _session_to_dict(self, s: ReplaySession) -> dict:
        return {
            "id": s.id,
            "instrument": s.instrument,
            "timeframe": s.timeframe,
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "mode": s.mode,
            "status": s.status,
            "bar_count": s.bar_count,
            "bar_index": s.bar_index,
            "current_timestamp": s.current_timestamp.isoformat() if s.current_timestamp else None,
            "config_json": s.config_json,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }

    # ── Snapshots ──────────────────────────────────────────

    async def store_snapshot(self, replay_id: int, snapshot: dict) -> int:
        """Store a single replay snapshot."""
        import json as _json
        db_snapshot = SnapshotModel(
            replay_id=replay_id,
            bar_index=snapshot["bar_index"],
            timestamp=datetime.fromisoformat(snapshot["current_timestamp"]) if snapshot.get("current_timestamp") else datetime.utcnow(),
            candle_json=_json.dumps(snapshot.get("candle", {})),
            summary_json=_json.dumps({
                "instrument": snapshot.get("instrument", ""),
                "timeframe": snapshot.get("timeframe", ""),
                "active_liquidity_count": snapshot.get("active_liquidity_count", 0),
                "active_fvg_count": snapshot.get("active_fvg_count", 0),
                "active_ob_count": snapshot.get("active_ob_count", 0),
                "active_smt_count": snapshot.get("active_smt_count", 0),
                "confluence_snapshot_ref": snapshot.get("confluence_snapshot_ref"),
                "market_bias": snapshot.get("market_bias", {}),
                "trade_setup_ref": snapshot.get("trade_setup_ref"),
                "risk_report_ref": snapshot.get("risk_report_ref"),
                "position_sizing_ref": snapshot.get("position_sizing_ref"),
                "trade_mgmt_state_ref": snapshot.get("trade_mgmt_state_ref"),
            }, default=str),
        )
        self.session.add(db_snapshot)
        await self.session.flush()
        return db_snapshot.id

    async def store_snapshots_bulk(self, replay_id: int, snapshots: list[dict]) -> int:
        """Bulk insert snapshots."""
        import json as _json
        count = 0
        for snap in snapshots:
            db_snapshot = SnapshotModel(
                replay_id=replay_id,
                bar_index=snap["bar_index"],
                timestamp=datetime.fromisoformat(snap["current_timestamp"]) if snap.get("current_timestamp") else datetime.utcnow(),
                candle_json=_json.dumps(snap.get("candle", {})),
                summary_json=_json.dumps(snap, default=str),
            )
            self.session.add(db_snapshot)
            count += 1
        await self.session.flush()
        return count

    async def get_snapshots(
        self, replay_id: int, limit: int = 500,
    ) -> list[dict]:
        """Get snapshots for a replay session."""
        result = await self.session.execute(
            select(SnapshotModel)
            .where(SnapshotModel.replay_id == replay_id)
            .order_by(SnapshotModel.bar_index.asc())
            .limit(limit)
        )
        return [
            {
                "id": s.id, "replay_id": s.replay_id,
                "bar_index": s.bar_index,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                "candle_json": s.candle_json,
                "summary_json": s.summary_json,
            }
            for s in result.scalars().all()
        ]

    # ── Events ─────────────────────────────────────────────

    async def store_event(self, replay_id: int, event: dict) -> int:
        """Store a single replay event."""
        import json as _json
        db_event = EventModel(
            replay_id=replay_id,
            bar_index=event["bar_index"],
            timestamp=datetime.fromisoformat(event["timestamp"]) if event.get("timestamp") else datetime.utcnow(),
            engine_source=event.get("engine_source", ""),
            event_type=event.get("event_type", ""),
            entity_ids_json=_json.dumps(event.get("entity_ids", [])),
            detail=event.get("detail", ""),
        )
        self.session.add(db_event)
        await self.session.flush()
        return db_event.id

    async def store_events_bulk(self, replay_id: int, events: list[dict]) -> int:
        """Bulk insert events."""
        import json as _json
        count = 0
        for evt in events:
            db_event = EventModel(
                replay_id=replay_id,
                bar_index=evt["bar_index"],
                timestamp=datetime.fromisoformat(evt["timestamp"]) if evt.get("timestamp") else datetime.utcnow(),
                engine_source=evt.get("engine_source", ""),
                event_type=evt.get("event_type", ""),
                entity_ids_json=_json.dumps(evt.get("entity_ids", [])),
                detail=evt.get("detail", ""),
            )
            self.session.add(db_event)
            count += 1
        await self.session.flush()
        return count

    async def get_events(
        self, replay_id: int | None = None, engine_source: str | None = None,
        event_type: str | None = None, limit: int = 1000,
    ) -> list[dict]:
        """Get events with optional filters."""
        conditions = []
        if replay_id is not None:
            conditions.append(EventModel.replay_id == replay_id)
        if engine_source:
            conditions.append(EventModel.engine_source == engine_source)
        if event_type:
            conditions.append(EventModel.event_type == event_type)

        query = select(EventModel).order_by(desc(EventModel.created_at)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return [
            {
                "id": e.id, "replay_id": e.replay_id,
                "bar_index": e.bar_index,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "engine_source": e.engine_source,
                "event_type": e.event_type,
                "entity_ids_json": e.entity_ids_json,
                "detail": e.detail,
            }
            for e in result.scalars().all()
        ]

    # ── Statistics ─────────────────────────────────────────

    async def get_statistics(self, instrument: str) -> dict:
        """Get replay statistics for an instrument."""
        result = await self.session.execute(
            select(ReplaySession).where(ReplaySession.instrument == instrument.upper())
        )
        sessions = list(result.scalars().all())

        total = len(sessions)
        by_status = {}
        total_bars = 0
        for s in sessions:
            by_status[s.status] = by_status.get(s.status, 0) + 1
            total_bars += s.bar_count

        return {
            "instrument": instrument.upper(),
            "total_sessions": total,
            "by_status": by_status,
            "total_bars_replayed": total_bars,
        }
