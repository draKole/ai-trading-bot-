"""Trading Mode API — PAPER/LIVE switching with safety confirmation."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.mode import get_mode_manager

router = APIRouter()


@router.get("/mode")
async def get_mode():
    """Get current trading mode and kill switch status."""
    mgr = get_mode_manager()
    return mgr.state


@router.post("/mode/switch")
async def switch_mode(
    target: str = Query(..., description="Target mode: paper or live"),
    confirm: bool = Query(False, description="Must be true to execute the switch"),
):
    """Switch trading mode. Requires explicit confirm=true for safety.

    Paper → Live: enables live broker connectivity
    Live → Paper: disconnects from broker, safe mode

    Always returns current state — if confirm is False, returns
    status=confirmation_required without switching.
    """
    mgr = get_mode_manager()
    try:
        result = mgr.switch_mode(target, confirm=confirm)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


@router.post("/mode/kill")
async def kill_switch():
    """Global kill switch — halts ALL trading (paper and live).

    IRREVERSIBLE for the session. All orders cancelled, all positions
    flattened as soon as the next check runs.
    """
    mgr = get_mode_manager()
    result = mgr.kill()
    return result


@router.get("/mode/can-trade")
async def can_trade():
    """Check if trading is currently allowed."""
    mgr = get_mode_manager()
    allowed, reason = mgr.check_can_trade()
    return {"allowed": allowed, "reason": reason}
