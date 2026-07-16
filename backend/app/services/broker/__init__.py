"""Broker Adapter — abstract interface for broker integrations.

The core strategy engine NEVER talks to a broker directly.
It emits OrderRequests — data objects. The adapter translates
them into broker-specific API calls.

Supported adapters (future):
    - PaperAdapter (simulated fills — default)
    - IBKRAdapter (Interactive Brokers via ib_insync)
    - TradovateAdapter, RithmicAdapter, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class TimeInForce(str, Enum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class OrderRequest:
    """Broker-agnostic order request."""
    request_id: str
    instrument: str
    direction: Direction
    order_type: OrderType
    quantity: int
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    strategy_version: str = ""
    signal_id: str = ""


@dataclass
class OrderResponse:
    """Response from broker after order placement."""
    request_id: str
    broker_order_id: str
    status: str  # "filled", "partial", "rejected", "pending"
    filled_qty: int = 0
    avg_fill_price: float | None = None


@dataclass
class AccountSummary:
    balance: float
    equity: float
    margin_used: float
    open_positions: int
    daily_pnl: float


class BrokerAdapter(ABC):
    """All broker integrations implement this interface."""

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> OrderResponse: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> OrderResponse: ...

    @abstractmethod
    async def get_account_summary(self) -> AccountSummary: ...

    @abstractmethod
    async def is_connected(self) -> bool: ...
