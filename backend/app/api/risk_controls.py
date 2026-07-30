"""Execution Risk Controls API — kill switch, circuit breaker, daily loss, max position."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.risk.controls import ExecutionRiskController, ExecutionRiskConfig

router = APIRouter()

# Global execution risk controller
_risk_controller = ExecutionRiskController()


@router.get("/risk/controls")
async def get_risk_controls():
    """Get current risk control status: kill switch, circuit breaker, daily loss, positions."""
    return _risk_controller.get_status()


@router.post("/risk/controls/kill")
async def activate_kill_switch():
    """Activate execution kill switch — halts all order execution.

    IRREVERSIBLE for this session.
    """
    result = _risk_controller.kill()
    return result


@router.post("/risk/controls/config")
async def update_risk_config(
    daily_loss_limit: Optional[float] = Query(None, ge=0),
    circuit_breaker_consecutive_losses: Optional[int] = Query(None, ge=1),
    circuit_breaker_window_seconds: Optional[int] = Query(None, ge=10),
    max_pos_es: Optional[int] = Query(None, ge=1),
    max_pos_nq: Optional[int] = Query(None, ge=1),
    max_pos_mnq: Optional[int] = Query(None, ge=1),
    kill_switch_enabled: Optional[bool] = Query(None),
    circuit_breaker_enabled: Optional[bool] = Query(None),
    daily_loss_limit_enabled: Optional[bool] = Query(None),
    max_position_enabled: Optional[bool] = Query(None),
):
    """Update risk control parameters at runtime."""
    cfg = _risk_controller.config
    if daily_loss_limit is not None:
        cfg.daily_loss_limit = daily_loss_limit
        _risk_controller._daily_loss.limit = daily_loss_limit
    if circuit_breaker_consecutive_losses is not None:
        cfg.circuit_breaker_consecutive_losses = circuit_breaker_consecutive_losses
        _risk_controller._circuit_breaker.max_consecutive = circuit_breaker_consecutive_losses
    if circuit_breaker_window_seconds is not None:
        cfg.circuit_breaker_window_seconds = circuit_breaker_window_seconds
        _risk_controller._circuit_breaker.window_seconds = circuit_breaker_window_seconds
    if max_pos_es is not None:
        cfg.max_position_size["ES"] = max_pos_es
    if max_pos_nq is not None:
        cfg.max_position_size["NQ"] = max_pos_nq
    if max_pos_mnq is not None:
        cfg.max_position_size["MNQ"] = max_pos_mnq
    if kill_switch_enabled is not None:
        cfg.kill_switch_enabled = kill_switch_enabled
    if circuit_breaker_enabled is not None:
        cfg.circuit_breaker_enabled = circuit_breaker_enabled
    if daily_loss_limit_enabled is not None:
        cfg.daily_loss_limit_enabled = daily_loss_limit_enabled
    if max_position_enabled is not None:
        cfg.max_position_enabled = max_position_enabled

    return {"status": "updated", "config": cfg.to_dict()}


@router.post("/risk/controls/record-trade")
async def record_trade_pnl(
    pnl: float = Query(...),
):
    """Record a completed trade P&L for circuit breaker / daily loss tracking.

    Positive = profit, negative = loss.
    """
    _risk_controller.record_trade(pnl)
    return {
        "status": "recorded",
        "pnl": pnl,
        "circuit_breaker_losses": _risk_controller._circuit_breaker.consecutive_losses,
        "daily_loss": round(_risk_controller._daily_loss.current_loss, 2),
        "killed": _risk_controller.is_killed,
    }
