"""Backtesting Engine — deterministic strategy evaluation over historical data.

Wraps the Phase 5A ReplayController. Supports single runs, batch runs,
parameter sweeps, and full performance metrics.

Components:
    - BacktestController: Orchestrator wrapping ReplayController
    - BacktestConfig / ParamSweepConfig: Configuration
    - compute_metrics: Deterministic metric calculation
    - BacktestingService: Persistence layer
"""

from app.services.backtesting.engine import (
    BacktestController, BacktestConfig, ParamSweepConfig,
    BacktestTrade, BacktestMetrics, BacktestResult, EquityPoint,
    compute_metrics,
)
from app.services.backtesting.service import BacktestingService

__all__ = [
    "BacktestController", "BacktestConfig", "ParamSweepConfig",
    "BacktestTrade", "BacktestMetrics", "BacktestResult", "EquityPoint",
    "compute_metrics", "BacktestingService",
]
