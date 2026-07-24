"""Phase 6B Tests — Broker Adapter & Live Trading Engine.

Tests for BrokerAdapter interface, Tradovate adapter, LiveTradingController,
safety controls, order lifecycle, and API integration.
"""

import json
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.broker.base import (
    BrokerAdapter, BrokerOrder, BrokerPosition, BrokerAccount, BrokerEvent,
    ConnectionState, OrderAction, OrderType, OrderStatus, BrokerEventType,
)
from app.services.broker.tradovate import TradovateAdapter
from app.services.live_trading.engine import (
    LiveTradingController, LiveTradingConfig, LiveTradingSession,
    SafetyController,
)


# ─── Helpers ─────────────────────────────────────────────────

def _make_config() -> LiveTradingConfig:
    return LiveTradingConfig(
        account_id=str(uuid4()), broker="tradovate",
        initial_balance=100_000.0,
    )


# ─── Broker Models Tests ────────────────────────────────────

class TestBrokerModels:
    """BrokerOrder, BrokerPosition, BrokerAccount, BrokerEvent."""

    def test_broker_order_defaults(self):
        order = BrokerOrder()
        assert order.order_type == "market"
        assert order.status == "pending"

    def test_broker_order_to_dict(self):
        order = BrokerOrder(instrument="ES", action="buy", quantity=2)
        d = order.to_dict()
        assert d["instrument"] == "ES"
        assert d["quantity"] == 2

    def test_broker_position_to_dict(self):
        pos = BrokerPosition(instrument="ES", quantity=3, avg_entry_price=6000.0)
        d = pos.to_dict()
        assert d["instrument"] == "ES"

    def test_broker_account_to_dict(self):
        acct = BrokerAccount(account_id="a1", balance=100_000.0)
        d = acct.to_dict()
        assert d["balance"] == 100_000.0

    def test_broker_event_to_dict(self):
        evt = BrokerEvent(event_type="connection", detail="Connected")
        d = evt.to_dict()
        assert d["event_type"] == "connection"


# ─── Broker Adapter Interface ──────────────────────────────

class TestBrokerAdapter:
    """Abstract BrokerAdapter interface — tested via TradovateAdapter."""

    def test_default_state(self):
        adapter = TradovateAdapter()
        assert adapter.state == "disconnected"
        assert adapter.events == []

    def test_emit_event(self):
        adapter = TradovateAdapter()
        event = adapter._emit_event("connection", "test")
        assert len(adapter.events) == 1
        assert event.event_type == "connection"

    def test_callback_registration(self):
        adapter = TradovateAdapter()
        received = []
        adapter.register_callback(lambda e: received.append(e))
        adapter._emit_event("test_event", "data")
        assert len(received) == 1


# ─── Tradovate Adapter ─────────────────────────────────────

class TestTradovateAdapter:
    """Tradovate adapter implementation."""

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        adapter = TradovateAdapter()
        ok = await adapter.connect()
        assert ok is True
        assert await adapter.is_connected() is True
        await adapter.disconnect()
        assert await adapter.is_connected() is False

    @pytest.mark.asyncio
    async def test_place_market_order(self):
        adapter = TradovateAdapter()
        await adapter.connect()
        order = BrokerOrder(action="buy", instrument="ES",
                           quantity=2, order_type="market")
        result = await adapter.place_order(order)
        assert result.status == "filled"
        assert result.broker_order_id != ""
        assert result.filled_qty == 2

    @pytest.mark.asyncio
    async def test_place_order_while_disconnected(self):
        adapter = TradovateAdapter()
        order = BrokerOrder(action="buy", instrument="ES", quantity=1)
        result = await adapter.place_order(order)
        assert result.status == "rejected"

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        adapter = TradovateAdapter()
        await adapter.connect()
        order = BrokerOrder(action="buy", instrument="ES", quantity=1,
                           order_type="limit", limit_price=6000.0)
        result = await adapter.place_order(order)
        ok = await adapter.cancel_order(result.order_id)
        assert ok is True

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        adapter = TradovateAdapter()
        await adapter.connect()
        ok = await adapter.cancel_order("nonexistent")
        assert ok is False

    @pytest.mark.asyncio
    async def test_get_positions(self):
        adapter = TradovateAdapter()
        await adapter.connect()
        order = BrokerOrder(action="buy", instrument="ES", quantity=3)
        await adapter.place_order(order)
        positions = await adapter.get_positions()
        assert len(positions) >= 1

    @pytest.mark.asyncio
    async def test_get_account(self):
        adapter = TradovateAdapter({"initial_balance": 50_000.0})
        acct = await adapter.get_account()
        assert acct.balance == 50_000.0

    @pytest.mark.asyncio
    async def test_modify_order(self):
        adapter = TradovateAdapter()
        await adapter.connect()
        order = BrokerOrder(action="buy", instrument="ES", quantity=1,
                           order_type="limit", limit_price=6000.0)
        result = await adapter.place_order(order)
        updated = await adapter.modify_order(result.order_id,
                                              {"limit_price": 6010.0})
        assert updated is not None
        assert updated.limit_price == 6010.0


# ─── Live Trading Controller ───────────────────────────────

class TestLiveTradingController:
    """Controller lifecycle and order routing."""

    @pytest.mark.asyncio
    async def test_create_and_connect(self):
        controller = LiveTradingController()
        config = _make_config()
        adapter = TradovateAdapter(config.to_dict())
        session = controller.create_session(config, adapter)
        ok = await controller.connect(config.account_id)
        assert ok is True
        assert session.connection_state == "connected"

    @pytest.mark.asyncio
    async def test_disconnect(self):
        controller = LiveTradingController()
        config = _make_config()
        adapter = TradovateAdapter(config.to_dict())
        controller.create_session(config, adapter)
        await controller.connect(config.account_id)
        ok = await controller.disconnect(config.account_id)
        assert ok is True

    @pytest.mark.asyncio
    async def test_place_order(self):
        controller = LiveTradingController()
        config = _make_config()
        adapter = TradovateAdapter(config.to_dict())
        controller.create_session(config, adapter)
        await controller.connect(config.account_id)
        order = BrokerOrder(action="buy", instrument="ES", quantity=1)
        result = await controller.place_order(config.account_id, order)
        assert result["status"] == "filled"

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        controller = LiveTradingController()
        config = _make_config()
        adapter = TradovateAdapter(config.to_dict())
        controller.create_session(config, adapter)
        await controller.connect(config.account_id)
        order = BrokerOrder(action="buy", instrument="ES", quantity=1,
                           order_type="limit", limit_price=6000.0)
        result = await controller.place_order(config.account_id, order)
        cancel_result = await controller.cancel_order(
            config.account_id, result["order"]["order_id"])
        assert cancel_result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_sync_positions(self):
        controller = LiveTradingController()
        config = _make_config()
        adapter = TradovateAdapter(config.to_dict())
        controller.create_session(config, adapter)
        await controller.connect(config.account_id)
        order = BrokerOrder(action="buy", instrument="ES", quantity=2)
        await controller.place_order(config.account_id, order)
        await controller.sync_positions(config.account_id)
        session = controller.get_session(config.account_id)
        assert len(session.open_positions) >= 1

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        controller = LiveTradingController()
        config1 = _make_config()
        config2 = _make_config()
        controller.create_session(config1)
        controller.create_session(config2)
        sessions = controller.list_sessions()
        assert len(sessions) == 2

    def test_get_nonexistent(self):
        controller = LiveTradingController()
        assert controller.get_session("nonexistent") is None


# ─── Safety Controller ─────────────────────────────────────

class TestSafetyController:
    """Safety limits and kill switch."""

    def test_duplicate_prevention(self):
        config = LiveTradingConfig(duplicate_order_prevention=True)
        safety = SafetyController(config)
        session = LiveTradingSession(connection_state="connected")
        order = BrokerOrder(order_id="test-1")
        ok1, _ = safety.check_order(order, session)
        ok2, _ = safety.check_order(order, session)
        assert ok1 is True
        assert ok2 is False  # Duplicate

    def test_max_positions(self):
        config = LiveTradingConfig(max_open_positions=1)
        safety = SafetyController(config)
        session = LiveTradingSession(connection_state="connected",
                                      open_positions=[BrokerPosition()] * 1)
        order = BrokerOrder(order_id="new")
        ok, reason = safety.check_order(order, session)
        assert ok is False
        assert "Max open positions" in reason

    def test_kill_switch(self):
        config = LiveTradingConfig()
        safety = SafetyController(config)
        session = LiveTradingSession(connection_state="connected")
        safety.emergency_stop(session)
        assert session.killed is True

    def test_killed_session_rejects_orders(self):
        config = LiveTradingConfig()
        safety = SafetyController(config)
        session = LiveTradingSession(connection_state="connected", killed=True)
        order = BrokerOrder(order_id="test-1")
        ok, reason = safety.check_order(order, session)
        assert ok is False
        assert "kill switch" in reason.lower()

    def test_disconnected_session_rejects(self):
        config = LiveTradingConfig()
        safety = SafetyController(config)
        session = LiveTradingSession(connection_state="disconnected")
        order = BrokerOrder(order_id="test-1")
        ok, _ = safety.check_order(order, session)
        assert ok is False

    def test_daily_loss_limit(self):
        config = LiveTradingConfig(max_daily_loss=500.0)
        safety = SafetyController(config)
        session = LiveTradingSession(connection_state="connected",
                                      daily_loss=400.0)
        safety.record_loss(400.0)
        order = BrokerOrder(order_id="test-1")
        ok, _ = safety.check_order(order, session)
        assert ok is False


# ─── Determinism ───────────────────────────────────────────

class TestDeterminism:
    """Deterministic behavior."""

    def test_broker_order_deterministic(self):
        o1 = BrokerOrder(action="buy", instrument="ES", quantity=2)
        o2 = BrokerOrder(action="buy", instrument="ES", quantity=2)
        assert o1.action == o2.action
        assert o1.quantity == o2.quantity


# ─── Serialization ─────────────────────────────────────────

class TestSerialization:
    """Config and session serialization."""

    def test_live_config_roundtrip(self):
        config = _make_config()
        d = config.to_dict()
        restored = LiveTradingConfig.from_dict(d)
        assert restored.max_daily_loss == config.max_daily_loss
        assert restored.duplicate_order_prevention == config.duplicate_order_prevention

    def test_live_session_to_dict(self):
        session = LiveTradingSession(account_id="test", balance=50_000.0)
        d = session.to_dict()
        assert d["account_id"] == "test"
        assert d["balance"] == 50_000.0


# ─── API Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_live_sessions_api():
    """Test /api/v1/live/sessions endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/live/sessions")
            assert response.status_code == 200
            data = response.json()
            assert "count" in data
    except ConnectionRefusedError:
        pytest.skip("Database not available")
