"""Trade Management Engine — lifecycle state machine for active trades.

Consumes Trade Setup + Risk Report + Position Recommendation + market bars
to manage trade state. Advisory only — no broker communication.

Components:
    - init_trade: Create a ManagedTrade from setup
    - enter_trade: Transition from pending to active
    - process_bar: Evaluate a bar (stops, targets, breakeven, trailing, time)
    - cancel_trade / expire_trade: Terminal states
    - TradeManagementService: Persistence layer
"""

from app.services.trade_management.engine import (
    init_trade, enter_trade, process_bar,
    cancel_trade, expire_trade,
    ManagedTrade, TradeEvent, Bar,
    TradeManagementConfig, TradeState, ExitReason,
)
from app.services.trade_management.service import TradeManagementService

__all__ = [
    "init_trade", "enter_trade", "process_bar",
    "cancel_trade", "expire_trade",
    "ManagedTrade", "TradeEvent", "Bar",
    "TradeManagementConfig", "TradeState", "ExitReason",
    "TradeManagementService",
]
