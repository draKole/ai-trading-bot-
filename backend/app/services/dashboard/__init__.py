"""Operator Dashboard — read-only aggregation of platform state."""

from app.services.dashboard.engine import (
    DashboardController, TimelineEvent, WidgetData,
)
from app.services.dashboard.service import DashboardService

__all__ = [
    "DashboardController", "TimelineEvent", "WidgetData", "DashboardService",
]
