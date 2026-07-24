"""Broker Adapter — Abstract interface for live broker connectivity.

All broker implementations (Tradovate, IBKR, etc.) MUST implement this interface.
Only the BrokerAdapter talks to external APIs — no pipeline code calls
external services directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class OrderAction(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    WORKING = "working"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BrokerEventType(str, Enum):
    ORDER_ACCEPTED = "order_accepted"
    PARTIAL_FILL = "partial_fill"
    FULL_FILL = "full_fill"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    MODIFIED = "modified"
    POSITION_UPDATE = "position_update"
    CONNECTION_LOST = "connection_lost"
    RECONNECTED = "reconnected"
    HEARTBEAT = "heartbeat"


@dataclass
class BrokerOrder:
    """Standardized order representation across all brokers."""
    order_id: str = field(default_factory=lambda: str(uuid4()))
    broker_order_id: str = ""
    instrument: str = ""
    action: str = "buy"
    order_type: str = "market"
    quantity: int = 1
    limit_price: float | None = None
    stop_price: float | None = None
    status: str = "pending"
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id, "broker_order_id": self.broker_order_id,
            "instrument": self.instrument, "action": self.action,
            "order_type": self.order_type, "quantity": self.quantity,
            "limit_price": self.limit_price, "stop_price": self.stop_price,
            "status": self.status, "filled_qty": self.filled_qty,
            "avg_fill_price": self.avg_fill_price,
        }


@dataclass
class BrokerPosition:
    """Standardized position from broker."""
    instrument: str = ""
    direction: str = "long"
    quantity: int = 0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument, "direction": self.direction,
            "quantity": self.quantity, "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
        }


@dataclass
class BrokerAccount:
    """Account information from broker."""
    account_id: str = ""
    name: str = ""
    balance: float = 0.0
    buying_power: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id, "name": self.name,
            "balance": self.balance, "buying_power": self.buying_power,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
        }


@dataclass
class BrokerEvent:
    """Timestamped broker event."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = ""
    detail: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id, "event_type": self.event_type,
            "detail": self.detail,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


class BrokerAdapter(ABC):
    """Abstract interface for broker connectivity.

    All live broker implementations MUST implement this interface.
    The pipeline code only calls methods on this interface — never
    calls broker APIs directly.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._events: list[BrokerEvent] = []
        self._event_callbacks: list[Any] = []

    @property
    def state(self) -> str:
        return self._state.value

    @property
    def events(self) -> list[BrokerEvent]:
        return list(self._events)

    def register_callback(self, callback) -> None:
        """Register a callback for broker events."""
        self._event_callbacks.append(callback)

    def _emit_event(self, event_type: str, detail: str = "",
                    data: dict | None = None) -> BrokerEvent:
        event = BrokerEvent(event_type=event_type, detail=detail, data=data or {})
        self._events.append(event)
        for cb in self._event_callbacks:
            try:
                cb(event)
            except Exception:
                pass
        return event

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the broker. Returns True on success."""
        ...

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the broker."""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check connection status."""
        ...

    @abstractmethod
    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        """Place an order. Returns updated order with broker_order_id."""
        ...

    @abstractmethod
    async def modify_order(self, order_id: str, updates: dict) -> BrokerOrder | None:
        """Modify an existing order."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        ...

    @abstractmethod
    async def get_order(self, order_id: str) -> BrokerOrder | None:
        """Get order status."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Get current positions."""
        ...

    @abstractmethod
    async def get_account(self) -> BrokerAccount:
        """Get account information."""
        ...

    async def get_account_summary(self) -> dict:
        """Get account summary as dict (convenience wrapper)."""
        acct = await self.get_account()
        return acct.to_dict() if acct else {}

    @abstractmethod
    async def get_market_price(self, instrument: str) -> float | None:
        """Get current market price for an instrument."""
        ...
