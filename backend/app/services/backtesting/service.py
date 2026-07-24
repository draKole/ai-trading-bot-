"""Backtesting Persistence Service — CRUD for runs, trades, and metrics."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, and_, desc

from app.models.backtesting import (
    BacktestRun, BacktestTrade as TradeModel, BacktestMetrics as MetricsModel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class BacktestingService:
    """Service for backtest run, trade, and metrics persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Runs ───────────────────────────────────────────────

    async def create_run(self, config: dict) -> dict:
        """Create a new backtest run."""
        import json as _json
        db_run = BacktestRun(
            instrument=config["instrument"],
            timeframe=config.get("timeframe", "5m"),
            start_time=config["start_time"],
            end_time=config["end_time"],
            status="pending",
            total_bars=0,
            config_json=_json.dumps(config, default=str),
        )
        self.session.add(db_run)
        await self.session.flush()
        return {
            "id": db_run.id,
            "instrument": db_run.instrument,
            "timeframe": db_run.timeframe,
            "status": db_run.status,
        }

    async def update_run(self, run_id: int, updates: dict) -> dict | None:
        """Update a backtest run."""
        result = await self.session.execute(
            select(BacktestRun).where(BacktestRun.id == run_id)
        )
        db_run = result.scalar_one_or_none()
        if db_run is None:
            return None
        for key, value in updates.items():
            if hasattr(db_run, key):
                setattr(db_run, key, value)
        await self.session.flush()
        return {"id": db_run.id, "status": db_run.status}

    async def get_run(self, run_id: int) -> dict | None:
        """Get a backtest run by ID."""
        result = await self.session.execute(
            select(BacktestRun).where(BacktestRun.id == run_id)
        )
        db_run = result.scalar_one_or_none()
        if db_run is None:
            return None
        return self._run_to_dict(db_run)

    async def get_runs(
        self, instrument: str | None = None, status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List backtest runs with filters."""
        conditions = []
        if instrument:
            conditions.append(BacktestRun.instrument == instrument.upper())
        if status:
            conditions.append(BacktestRun.status == status)

        query = select(BacktestRun).order_by(desc(BacktestRun.created_at)).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return [self._run_to_dict(r) for r in result.scalars().all()]

    def _run_to_dict(self, r: BacktestRun) -> dict:
        return {
            "id": r.id,
            "instrument": r.instrument,
            "timeframe": r.timeframe,
            "start_time": r.start_time.isoformat() if r.start_time else None,
            "end_time": r.end_time.isoformat() if r.end_time else None,
            "status": r.status,
            "total_bars": r.total_bars,
            "config_json": r.config_json,
            "metrics_json": r.metrics_json,
            "equity_curve_json": r.equity_curve_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }

    # ── Trades ─────────────────────────────────────────────

    async def store_trades_bulk(self, run_id: int, trades: list[dict]) -> int:
        """Bulk insert trades."""
        count = 0
        for t in trades:
            db_trade = TradeModel(
                run_id=run_id,
                entry_time=datetime.fromisoformat(t["entry_time"]) if t.get("entry_time") else datetime.utcnow(),
                exit_time=datetime.fromisoformat(t["exit_time"]) if t.get("exit_time") else datetime.utcnow(),
                direction=t.get("direction", ""),
                quantity=t.get("quantity", 1),
                entry_price=t.get("entry_price", 0),
                exit_price=t.get("exit_price", 0),
                stop_price=t.get("stop_price", 0),
                risk=t.get("risk", 0),
                r_multiple=t.get("r_multiple", 0),
                pnl=t.get("pnl", 0),
                duration_seconds=t.get("duration_seconds", 0),
                exit_reason=t.get("exit_reason", ""),
                strategy_version=t.get("strategy_version", "1.0.0"),
            )
            self.session.add(db_trade)
            count += 1
        await self.session.flush()
        return count

    async def get_trades(
        self, run_id: int | None = None, limit: int = 500,
    ) -> list[dict]:
        """Get trades with optional run filter."""
        conditions = []
        if run_id is not None:
            conditions.append(TradeModel.run_id == run_id)

        query = select(TradeModel).order_by(TradeModel.exit_time.asc()).limit(limit)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return [
            {
                "id": t.id, "run_id": t.run_id,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "direction": t.direction,
                "quantity": t.quantity,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "stop_price": t.stop_price,
                "risk": t.risk,
                "r_multiple": t.r_multiple,
                "pnl": t.pnl,
                "duration_seconds": t.duration_seconds,
                "exit_reason": t.exit_reason,
                "strategy_version": t.strategy_version,
            }
            for t in result.scalars().all()
        ]

    # ── Metrics ────────────────────────────────────────────

    async def store_metrics(self, run_id: int, metrics: dict) -> int:
        """Store aggregated metrics for a run."""
        db_metrics = MetricsModel(
            run_id=run_id,
            net_profit=metrics.get("net_profit", 0),
            gross_profit=metrics.get("gross_profit", 0),
            gross_loss=metrics.get("gross_loss", 0),
            total_trades=metrics.get("total_trades", 0),
            winning_trades=metrics.get("winning_trades", 0),
            losing_trades=metrics.get("losing_trades", 0),
            breakeven_trades=metrics.get("breakeven_trades", 0),
            win_rate=metrics.get("win_rate", 0),
            loss_rate=metrics.get("loss_rate", 0),
            profit_factor=metrics.get("profit_factor", 0),
            average_win=metrics.get("average_win", 0),
            average_loss=metrics.get("average_loss", 0),
            average_r=metrics.get("average_r", 0),
            expectancy=metrics.get("expectancy", 0),
            max_drawdown=metrics.get("max_drawdown", 0),
            max_drawdown_pct=metrics.get("max_drawdown_pct", 0),
            max_consecutive_wins=metrics.get("max_consecutive_wins", 0),
            max_consecutive_losses=metrics.get("max_consecutive_losses", 0),
            average_trade_duration_seconds=metrics.get("average_trade_duration_seconds", 0),
            long_trades=metrics.get("long_trades", 0),
            long_wins=metrics.get("long_wins", 0),
            long_pnl=metrics.get("long_pnl", 0),
            short_trades=metrics.get("short_trades", 0),
            short_wins=metrics.get("short_wins", 0),
            short_pnl=metrics.get("short_pnl", 0),
            largest_winner=metrics.get("largest_winner", 0),
            largest_loser=metrics.get("largest_loser", 0),
        )
        self.session.add(db_metrics)
        await self.session.flush()
        return db_metrics.id

    async def get_metrics(self, run_id: int) -> dict | None:
        """Get metrics for a run."""
        result = await self.session.execute(
            select(MetricsModel).where(MetricsModel.run_id == run_id)
        )
        m = result.scalar_one_or_none()
        if m is None:
            return None
        return {
            "id": m.id, "run_id": m.run_id,
            "net_profit": m.net_profit, "gross_profit": m.gross_profit,
            "gross_loss": m.gross_loss,
            "total_trades": m.total_trades,
            "winning_trades": m.winning_trades,
            "losing_trades": m.losing_trades,
            "breakeven_trades": m.breakeven_trades,
            "win_rate": m.win_rate, "loss_rate": m.loss_rate,
            "profit_factor": m.profit_factor,
            "average_win": m.average_win, "average_loss": m.average_loss,
            "average_r": m.average_r, "expectancy": m.expectancy,
            "max_drawdown": m.max_drawdown, "max_drawdown_pct": m.max_drawdown_pct,
            "max_consecutive_wins": m.max_consecutive_wins,
            "max_consecutive_losses": m.max_consecutive_losses,
            "average_trade_duration_seconds": m.average_trade_duration_seconds,
            "long_trades": m.long_trades, "long_wins": m.long_wins,
            "long_pnl": m.long_pnl,
            "short_trades": m.short_trades, "short_wins": m.short_wins,
            "short_pnl": m.short_pnl,
            "largest_winner": m.largest_winner, "largest_loser": m.largest_loser,
        }

    # ── Statistics ─────────────────────────────────────────

    async def get_statistics(self, instrument: str) -> dict:
        """Aggregated statistics across all runs for an instrument."""
        result = await self.session.execute(
            select(BacktestRun).where(BacktestRun.instrument == instrument.upper())
        )
        runs = list(result.scalars().all())
        total_runs = len(runs)
        completed = [r for r in runs if r.status == "completed"]

        return {
            "instrument": instrument.upper(),
            "total_runs": total_runs,
            "completed_runs": len(completed),
            "pending_runs": sum(1 for r in runs if r.status == "pending"),
            "failed_runs": sum(1 for r in runs if r.status == "failed"),
        }
