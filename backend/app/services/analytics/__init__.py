"""Performance Analytics Engine — deterministic analysis of completed backtests.

Consumes BacktestRun/BacktestTrade/BacktestMetrics from Phase 5B.
All calculations are pure functions.

Components:
    - AnalyticsController: orchestrates report generation and comparison
    - compute_sharpe_ratio / compute_sortino_ratio / compute_calmar_ratio
    - compute_drawdown_analytics / compute_returns_analytics / compute_trade_analytics
    - compute_rolling_analytics
    - generate_report / compare_strategies
    - AnalyticsService: persistence layer
"""

from app.services.analytics.engine import (
    AnalyticsController,
    compute_sharpe_ratio, compute_sortino_ratio, compute_calmar_ratio,
    compute_drawdown_analytics, compute_returns_analytics,
    compute_trade_analytics, compute_rolling_analytics,
    generate_report, compare_strategies,
)
from app.services.analytics.service import AnalyticsService

__all__ = [
    "AnalyticsController",
    "compute_sharpe_ratio", "compute_sortino_ratio", "compute_calmar_ratio",
    "compute_drawdown_analytics", "compute_returns_analytics",
    "compute_trade_analytics", "compute_rolling_analytics",
    "generate_report", "compare_strategies",
    "AnalyticsService",
]
