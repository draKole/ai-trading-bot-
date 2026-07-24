"""Paper Trading Engine — simulated execution with the real pipeline.

Components:
    - PaperTradingController: session, order, position, and execution management
    - PaperSession / PaperOrder / PaperPosition / PaperExecution dataclasses
    - Simulated order execution with slippage and commission
    - PaperTradingService: persistence layer
"""

from app.services.paper_trading.engine import (
    PaperTradingController, PaperTradingConfig,
    PaperSession, PaperOrder, PaperPosition, PaperExecution,
    execute_market_order, execute_limit_order,
    compute_slippage, compute_commission,
    update_position_after_fill, compute_unrealized_pnl,
    SessionStatus, OrderType, OrderSide, OrderStatus, PositionStatus,
)
from app.services.paper_trading.service import PaperTradingService

__all__ = [
    "PaperTradingController", "PaperTradingConfig",
    "PaperSession", "PaperOrder", "PaperPosition", "PaperExecution",
    "execute_market_order", "execute_limit_order",
    "compute_slippage", "compute_commission",
    "update_position_after_fill", "compute_unrealized_pnl",
    "SessionStatus", "OrderType", "OrderSide", "OrderStatus", "PositionStatus",
    "PaperTradingService",
]
