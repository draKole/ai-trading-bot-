"""Optimization ORM models — OptimizationRun, OptimizationResult, ParameterSet, WalkForwardRun, MonteCarloRun."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OptimizationRun(Base):
    """A single optimization run over parameter combinations."""

    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="grid")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    total_combinations: Mapped[int] = mapped_column(Integer, default=0)
    completed_combinations: Mapped[int] = mapped_column(Integer, default=0)
    best_params_json: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    best_score: Mapped[float] = mapped_column(Float, default=0.0)
    config_json: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ParameterSet(Base):
    """A parameter combination definition."""

    __tablename__ = "parameter_sets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("optimization_runs.id"), nullable=False, index=True,
    )
    params_json: Mapped[str] = mapped_column(String(2000), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class OptimizationResult(Base):
    """A single backtest result from a parameter combination."""

    __tablename__ = "optimization_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("optimization_runs.id"), nullable=False, index=True,
    )
    params_json: Mapped[str] = mapped_column(String(2000), nullable=False)
    metrics_json: Mapped[str] = mapped_column(String(5000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class WalkForwardRun(Base):
    """Walk-forward optimization run with in/out-of-sample windows."""

    __tablename__ = "walk_forward_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    window_count: Mapped[int] = mapped_column(Integer, default=0)
    in_sample_months: Mapped[int] = mapped_column(Integer, default=6)
    out_sample_months: Mapped[int] = mapped_column(Integer, default=2)
    stability_score: Mapped[float] = mapped_column(Float, default=0.0)
    results_json: Mapped[str | None] = mapped_column(String(10000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MonteCarloRun(Base):
    """Monte Carlo simulation results."""

    __tablename__ = "monte_carlo_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    iterations: Mapped[int] = mapped_column(Integer, default=1000)
    mean_equity: Mapped[float] = mapped_column(Float, default=0.0)
    equity_std: Mapped[float] = mapped_column(Float, default=0.0)
    risk_of_ruin: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_95_low: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_95_high: Mapped[float] = mapped_column(Float, default=0.0)
    results_json: Mapped[str | None] = mapped_column(String(20000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
