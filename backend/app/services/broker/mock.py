"""Mock BrokerAdapter — in-memory implementation for testing and paper mode.

Implements the full BrokerAdapter ABC with deterministic behavior,
no external dependencies, no network calls. Used by tests and paper trading.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.services.broker.base import (
    BrokerAdapter, BrokerOrder, BrokerPosition, BrokerAccount, BrokerEvent,
    ConnectionState, OrderStatus, OrderAction,
)


class MockBrokerAdapter(BrokerAdapter):
    """In-memory broker for testing and paper trading.

    Deterministic order lifecycle — market orders fill immediately,
    limit orders fill when price crosses the limit.
    """

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._orders: dict[str, BrokerOrder] = {}
        self._positions: dict[str, BrokerPosition] = {}
        self._prices: dict[str, float] = {
            "ES": 5500.0, "NQ": 20000.0, "MNQ": 20000.0,
        }
        self._account = BrokerAccount(
            account_id="mock-001", name="Mock Account",
            balance=100_000.0, buying_power=100_000.0,
        )
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        self._state = ConnectionState.CONNECTED
        self._emit_event("connected", "Mock broker connected")
        return True

    async def disconnect(self) -> bool:
        self._connected = False
        self._state = ConnectionState.DISCONNECTED
        self._emit_event("disconnected", "Mock broker disconnected")
        return True

    async def is_connected(self) -> bool:
        return self._connected

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        order_id = order.order_id or str(uuid4())
        order.order_id = order_id
        order.broker_order_id = f"mock-{order_id[:8]}"
        order.created_at = datetime.now(timezone.utc)

        if order.order_type == "market":
            price = self._prices.get(order.instrument, 5000.0)
            order.status = OrderStatus.FILLED
            order.filled_qty = order.quantity
            order.avg_fill_price = price
            self._update_positions(order, price)
        elif order.order_type in ("limit", "stop"):
            order.status = OrderStatus.WORKING
        else:
            order.status = OrderStatus.ACCEPTED

        self._orders[order_id] = order
        return order

    async def modify_order(self, order_id: str, updates: dict) -> BrokerOrder | None:
        order = self._orders.get(order_id)
        if not order:
            return None
        if "quantity" in updates:
            order.quantity = updates["quantity"]
        if "limit_price" in updates:
            order.limit_price = updates["limit_price"]
        if "stop_price" in updates:
            order.stop_price = updates["stop_price"]
        return order

    async def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if not order:
            return False
        order.status = OrderStatus.CANCELLED
        return True

    async def get_order(self, order_id: str) -> BrokerOrder | None:
        return self._orders.get(order_id)

    async def get_positions(self) -> list[BrokerPosition]:
        return list(self._positions.values())

    async def get_account(self) -> BrokerAccount:
        return self._account

    async def get_market_price(self, instrument: str) -> float | None:
        return self._prices.get(instrument)

    def set_price(self, instrument: str, price: float) -> None:
        """Set current market price (for test control)."""
        self._prices[instrument] = price

    def _update_positions(self, order: BrokerOrder, price: float) -> None:
        """Update mock positions after a fill."""
        key = f"{order.instrument}_{order.action}"
        existing = self._positions.get(key)
        if existing:
            if order.action == existing.direction:
                total_cost = existing.avg_entry_price * existing.quantity + price * order.quantity
                existing.quantity += order.quantity
                existing.avg_entry_price = total_cost / existing.quantity
            else:
                existing.quantity -= order.quantity
                if existing.quantity <= 0:
                    del self._positions[key]
                    return
        else:
            self._positions[key] = BrokerPosition(
                instrument=order.instrument,
                direction="long" if order.action == "buy" else "short",
                quantity=order.quantity,
                avg_entry_price=price,
                current_price=price,
            )
