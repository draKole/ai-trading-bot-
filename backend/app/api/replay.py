"""Historical Replay API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.replay import (
    ReplayService, ReplayController, ReplayConfig, OHLCVBar,
)

router = APIRouter()


# ─── Sessions ──────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    instrument: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List replay sessions."""
    service = ReplayService(db)
    sessions = await service.get_sessions(instrument=instrument, status=status, limit=limit)
    return {
        "count": len(sessions),
        "sessions": sessions,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a replay session by ID."""
    service = ReplayService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")
    return session


@router.post("/sessions/start")
async def start_replay(
    instrument: str = Query(...),
    timeframe: str = Query("5m"),
    start_time: str = Query(...),
    end_time: str = Query(...),
    mode: str = Query("candle_by_candle"),
    bars_json: Optional[str] = Query(None, description="JSON array of OHLCV bars"),
    db: AsyncSession = Depends(get_db),
):
    """Create a new replay session and optionally run a dry-run.

    If bars_json is provided, runs a full dry-run replay and returns
    the results. Otherwise, creates the session and returns its ID.
    """
    service = ReplayService(db)

    st = datetime.fromisoformat(start_time)
    et = datetime.fromisoformat(end_time)

    config = {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "start_time": st,
        "end_time": et,
        "mode": mode,
    }

    session_data = await service.create_session(config)
    session_id = session_data["id"]

    if bars_json:
        # Parse bars and run replay
        bar_dicts = json.loads(bars_json)
        bars = [OHLCVBar.from_dict(bd) for bd in bar_dicts]

        rc = ReplayConfig(
            instrument=instrument.upper(),
            timeframe=timeframe,
            start_time=st,
            end_time=et,
            mode=mode,
        )
        controller = ReplayController(rc)
        controller.load_bars(bars)
        snapshots = controller.dry_run()

        # Persist snapshots and events
        snapshot_dicts = [s.to_dict() for s in snapshots]
        event_dicts = [e.to_dict() for e in controller.events]

        # Update session
        bar_count = len(bars)
        await service.update_session(session_id, {
            "status": "stopped",
            "bar_count": bar_count,
            "bar_index": bar_count,
            "current_timestamp": et if controller.is_at_end else None,
        })

        if snapshots:
            await service.store_snapshots_bulk(session_id, snapshot_dicts)
        if event_dicts:
            await service.store_events_bulk(session_id, event_dicts)

        return {
            "session_id": session_id,
            "status": "completed",
            "mode": mode,
            "bar_count": bar_count,
            "snapshot_count": len(snapshots),
            "event_count": len(event_dicts),
            "snapshots": [
                {"bar_index": s.bar_index, "timestamp": s.current_timestamp.isoformat() if s.current_timestamp else None, "candle": s.candle}
                for s in snapshots[:100]  # Limit returned
            ],
        }

    return {
        "session_id": session_id,
        "status": "created",
        "mode": mode,
    }


# ─── Controls ──────────────────────────────────────────────

@router.post("/sessions/{session_id}/pause")
async def pause_replay(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Pause a running replay session."""
    service = ReplayService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")
    if session["status"] != "running":
        raise HTTPException(400, f"Session {session_id} is not running (status: {session['status']})")

    await service.update_session(session_id, {"status": "paused"})
    return {"session_id": session_id, "status": "paused"}


@router.post("/sessions/{session_id}/resume")
async def resume_replay(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused replay session."""
    service = ReplayService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")
    if session["status"] != "paused":
        raise HTTPException(400, f"Session {session_id} is not paused (status: {session['status']})")

    await service.update_session(session_id, {"status": "running"})
    return {"session_id": session_id, "status": "running"}


@router.post("/sessions/{session_id}/reset")
async def reset_replay(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Reset a replay session to idle."""
    service = ReplayService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")

    await service.update_session(session_id, {
        "status": "idle",
        "bar_index": 0,
        "current_timestamp": session["start_time"],
    })
    return {"session_id": session_id, "status": "idle"}


@router.post("/sessions/{session_id}/step")
async def step_replay(
    session_id: int,
    n: int = Query(1, ge=1, le=100, description="Number of bars to step"),
    db: AsyncSession = Depends(get_db),
):
    """Step forward N bars in a replay session."""
    service = ReplayService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")
    if session["status"] not in ("running", "paused"):
        raise HTTPException(400, f"Session {session_id} is not active (status: {session['status']})")

    # Load bars from config
    config = json.loads(session.get("config_json", "{}"))
    bar_dicts = config.get("_bars", [])
    bars = [OHLCVBar.from_dict(bd) for bd in bar_dicts] if bar_dicts else []

    rc = ReplayConfig(
        instrument=session["instrument"],
        timeframe=session["timeframe"],
        start_time=datetime.fromisoformat(session["start_time"]) if session["start_time"] else datetime.now(timezone.utc),
        end_time=datetime.fromisoformat(session["end_time"]) if session["end_time"] else datetime.now(timezone.utc),
        mode=session["mode"],
    )
    controller = ReplayController(rc)
    controller.load_bars(bars)
    controller._bar_index = session["bar_index"]
    controller._replay_id = session_id

    if session["status"] == "paused":
        controller._state = controller._state.__class__("paused")
    else:
        controller._state = controller._state.__class__("running")

    snapshots, is_end = controller.step(n)

    new_status = "stopped" if is_end else session["status"]
    await service.update_session(session_id, {
        "status": new_status,
        "bar_index": controller.bar_index,
        "current_timestamp": controller.current_bar.timestamp if controller.current_bar else None,
    })

    snapshot_dicts = [s.to_dict() for s in snapshots]
    if snapshot_dicts:
        await service.store_snapshots_bulk(session_id, snapshot_dicts)

    event_dicts = [e.to_dict() for e in controller.events]
    if event_dicts:
        await service.store_events_bulk(session_id, event_dicts)

    return {
        "session_id": session_id,
        "status": new_status,
        "bar_index": controller.bar_index,
        "bar_count": controller.bar_count,
        "progress_pct": controller.progress_pct,
        "stepped": len(snapshots),
        "is_at_end": is_end,
        "snapshots": [s.to_dict() for s in snapshots],
    }


# ─── Queries ───────────────────────────────────────────────

@router.get("/sessions/{session_id}/status")
async def get_replay_status(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get current replay session status."""
    service = ReplayService(db)
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")

    bar_count = session.get("bar_count", 0)
    bar_index = session.get("bar_index", 0)
    progress = round(bar_index / max(bar_count, 1) * 100, 1) if bar_count > 0 else 0.0

    return {
        "session_id": session_id,
        "status": session["status"],
        "instrument": session["instrument"],
        "timeframe": session["timeframe"],
        "mode": session["mode"],
        "bar_index": bar_index,
        "bar_count": bar_count,
        "progress_pct": progress,
        "current_timestamp": session.get("current_timestamp"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }


@router.get("/sessions/{session_id}/events")
async def get_replay_events(
    session_id: int,
    engine_source: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(1000, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Get events for a replay session."""
    service = ReplayService(db)
    events = await service.get_events(
        replay_id=session_id, engine_source=engine_source,
        event_type=event_type, limit=limit,
    )
    return {
        "session_id": session_id,
        "count": len(events),
        "events": events,
    }


@router.get("/sessions/{session_id}/snapshots")
async def get_replay_snapshots(
    session_id: int,
    limit: int = Query(500, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """Get snapshots for a replay session."""
    service = ReplayService(db)
    snapshots = await service.get_snapshots(replay_id=session_id, limit=limit)
    return {
        "session_id": session_id,
        "count": len(snapshots),
        "snapshots": snapshots,
    }


# ─── Dry Run (no DB persistence) ──────────────────────────

@router.post("/dry-run")
async def replay_dry_run(
    instrument: str = Query("ES"),
    timeframe: str = Query("5m"),
    start_time: str = Query("2025-06-16T09:30:00"),
    end_time: str = Query("2025-06-16T16:00:00"),
    mode: str = Query("candle_by_candle"),
    bars_json: str = Query(..., description="JSON array of OHLCV bars"),
):
    """Run a replay dry-run without persistence.

    Accepts a JSON array of bars and runs them through the replay engine.
    Returns all snapshots and events — deterministic output.
    """
    bar_dicts = json.loads(bars_json)
    bars = [OHLCVBar.from_dict(bd) for bd in bar_dicts]

    config = ReplayConfig(
        instrument=instrument.upper(),
        timeframe=timeframe,
        start_time=datetime.fromisoformat(start_time),
        end_time=datetime.fromisoformat(end_time),
        mode=mode,
    )

    controller = ReplayController(config)
    controller.load_bars(bars)
    snapshots = controller.dry_run()

    return {
        "instrument": instrument.upper(),
        "timeframe": timeframe,
        "mode": mode,
        "bar_count_input": len(bars),
        "bar_count_replayed": len(snapshots),
        "snapshots": [
            {
                "bar_index": s.bar_index,
                "timestamp": s.current_timestamp.isoformat() if s.current_timestamp else None,
                "candle": s.candle,
                "summary": s.to_dict(),
            }
            for s in snapshots
        ],
        "events": [e.to_dict() for e in controller.events],
    }
