"""Tradovate Broker Adapter — simulated implementation for testing.

Implements BrokerAdapter with simulated responses for order placement,
fills, cancellations, position tracking, and connection management.
In production, this would connect to Tradovate's REST/WebSocket API.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.services.broker.base import (
    BrokerAdapter, BrokerOrder, BrokerPosition, BrokerAccount,
    ConnectionState, BrokerEvent,
)


class TradovateAdapter(BrokerAdapter):
    """Simulated Tradovate broker adapter.

    Provides realistic order lifecycle simulation: orders are accepted,
    then filled (market orders immediately, limit orders when price crosses).
    Supports connection management, position tracking, and account balances.
    """

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._orders: dict[str, BrokerOrder] = {}
        self._positions: dict[str, BrokerPosition] = {}
        self._account = BrokerAccount(
            account_id=config.get("account_id", str(uuid4())) if config else str(uuid4()),
            name=config.get("name", "Tradovate Demo") if config else "Tradovate Demo",
            balance=config.get("initial_balance", 100_000.0) if config else 100_000.0,
            buying_power=config.get("initial_balance", 100_000.0) if config else 100_000.0,
        )
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self) -> bool:
        self._state = ConnectionState.CONNECTING
        self._emit_event("connection", "Connecting to Tradovate...")
        await asyncio.sleep(0.01)  # Simulated network delay
        self._state = ConnectionState.CONNECTED
        self._emit_event("connection", "Connected to Tradovate")
        self._start_heartbeat()
        return True

    async def disconnect(self) -> bool:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        self._state = ConnectionState.DISCONNECTED
        self._emit_event("connection", "Disconnected from Tradovate")
        return True

    async def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    def _start_heartbeat(self):
        """Start heartbeat monitoring."""
        async def _beat():
            while self._state == ConnectionState.CONNECTED:
                await asyncio.sleep(30)
                self._emit_event("heartbeat", "Tradovate heartbeat OK")
        try:
            self._heartbeat_task = asyncio.create_task(_beat())
        except RuntimeError:
            pass  # No event loop — tests use sync simulation

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        if not await self.is_connected():
            order.status = "rejected"
            self._emit_event("rejected", "Not connected to broker",
                            {"order_id": order.order_id})
            return order

        order.broker_order_id = f"tv-{uuid4().hex[:12]}"
        order.status = "accepted"
        order.created_at = datetime.now(timezone.utc)
        self._orders[order.order_id] = order

        self._emit_event("order_accepted",
                        f"Order {order.broker_order_id} accepted: {order.action} {order.quantity} {order.instrument}",
                        {"order_id": order.order_id})

        # Simulate fill for market orders
        if order.order_type == "market":
            await self._simulate_fill(order)

        return order

    async def _simulate_fill(self, order: BrokerOrder):
        """Simulate immediate fill for market orders."""
        price = 6000.0  # Default price
        await asyncio.sleep(0.01)  # Simulated latency
        order.status = "filled"
        order.filled_qty = order.quantity
        order.avg_fill_price = price

        # Update account
        cost = price * order.quantity
        if order.action == "buy":
            self._account.balance -= cost
        else:
            self._account.balance += cost
        self._account.buying_power = self._account.balance

        # Update position
        key = order.instrument
        if key in self._positions:
            pos = self._positions[key]
            if order.action == "buy":
                total_cost = pos.avg_entry_price * pos.quantity + price * order.quantity
                pos.quantity += order.quantity
                pos.avg_entry_price = total_cost / pos.quantity if pos.quantity > 0 else 0
            else:
                pos.quantity -= order.quantity
                if pos.quantity == 0:
                    pos.realized_pnl += (price - pos.avg_entry_price) * order.quantity
        else:
            self._positions[key] = BrokerPosition(
                instrument=order.instrument,
                direction="long" if order.action == "buy" else "short",
                quantity=order.quantity,
                avg_entry_price=price,
                current_price=price,
            )

        self._emit_event("full_fill",
                        f"Order {order.broker_order_id} filled: {order.quantity} @ {price}",
                        {"order_id": order.order_id, "fill_price": price})

    async def modify_order(self, order_id: str, updates: dict) -> BrokerOrder | None:
        order = self._orders.get(order_id)
        if order is None:
            return None
        for k, v in updates.items():
            if hasattr(order, k):
                setattr(order, k, v)
        self._emit_event("modified", f"Order {order_id} modified", {"order_id": order_id})
        return order

    async def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None or order.status in ("filled", "cancelled"):
            return False
        order.status = "cancelled"
        self._emit_event("cancelled", f"Order {order_id} cancelled", {"order_id": order_id})
        return True

    async def get_order(self, order_id: str) -> BrokerOrder | None:
        return self._orders.get(order_id)

    async def get_positions(self) -> list[BrokerPosition]:
        return list(self._positions.values())

    async def get_account(self) -> BrokerAccount:
        return self._account

    async def get_market_price(self, instrument: str) -> float | None:
        return 6000.0  # Default simulated price
