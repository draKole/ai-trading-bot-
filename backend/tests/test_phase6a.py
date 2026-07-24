"""Phase 6A Tests — Paper Trading Engine.

Tests for session lifecycle, order execution, fills, slippage, commission,
position management, statistics, and determinism.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.paper_trading.engine import (
    PaperTradingController, PaperTradingConfig,
    PaperSession, PaperOrder, PaperPosition, PaperExecution,
    execute_market_order, execute_limit_order,
    compute_slippage, compute_commission,
    update_position_after_fill, compute_unrealized_pnl,
)


# ─── Helpers ─────────────────────────────────────────────────

def _make_config(name: str = "Test", balance: float = 100_000.0) -> PaperTradingConfig:
    return PaperTradingConfig(
        account_id=str(uuid4()), name=name,
        initial_balance=balance,
    )


# ─── Config Tests ───────────────────────────────────────────

class TestConfig:
    """Config creation and serialization."""

    def test_default_config(self):
        config = PaperTradingConfig()
        assert config.initial_balance == 100_000.0

    def test_config_to_dict(self):
        config = _make_config()
        d = config.to_dict()
        assert d["name"] == "Test"

    def test_config_roundtrip(self):
        config = _make_config("Roundtrip", 50000.0)
        d = config.to_dict()
        restored = PaperTradingConfig.from_dict(d)
        assert restored.initial_balance == 50000.0
        assert restored.name == "Roundtrip"


# ─── Slippage / Commission ─────────────────────────────────

class TestSlippageCommission:
    """Slippage and commission calculations."""

    def test_slippage_buy_market(self):
        slip = compute_slippage("market", "buy", 100.0, 2, 0.25)
        assert slip == 0.5

    def test_slippage_sell_market(self):
        slip = compute_slippage("market", "sell", 100.0, 2, 0.25)
        assert slip == -0.5

    def test_slippage_limit_zero(self):
        slip = compute_slippage("limit", "buy", 100.0, 2, 0.25)
        assert slip == 0.0

    def test_commission(self):
        assert compute_commission(5, 2.50) == 12.50


# ─── Session Management ────────────────────────────────────

class TestSession:
    """Session lifecycle."""

    def test_create_session(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        assert session.status == "stopped"
        assert session.balance == 100_000.0

    def test_start_session(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        controller.start_session(session.account_id)
        assert session.status == "running"
        assert session.started_at is not None

    def test_pause_resume(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        controller.start_session(session.account_id)
        controller.pause_session(session.account_id)
        assert session.status == "paused"
        controller.resume_session(session.account_id)
        assert session.status == "running"

    def test_stop_session(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        controller.start_session(session.account_id)
        controller.stop_session(session.account_id)
        assert session.status == "stopped"

    def test_get_nonexistent_session(self):
        controller = PaperTradingController()
        assert controller.get_session("nonexistent") is None

    def test_list_sessions(self):
        controller = PaperTradingController()
        controller.create_session(_make_config("A"))
        controller.create_session(_make_config("B"))
        assert len(controller.list_sessions()) == 2

    def test_multiple_concurrent_sessions(self):
        controller = PaperTradingController()
        s1 = controller.create_session(_make_config("S1"))
        s2 = controller.create_session(_make_config("S2"))
        controller.start_session(s1.account_id)
        controller.start_session(s2.account_id)
        assert s1.status == "running"
        assert s2.status == "running"
        assert s1.account_id != s2.account_id


# ─── Order Execution ───────────────────────────────────────

class TestOrderExecution:
    """Order placement, fills, slippage, commission."""

    def test_execute_market_buy(self):
        order = PaperOrder(side="buy", instrument="ES",
                           quantity=2, order_type="market")
        config = _make_config()
        updated, execution = execute_market_order(order, 6000.0, config)
        assert updated.status == "filled"
        assert updated.filled_qty == 2
        assert updated.fill_price > 6000.0  # slippage
        assert updated.commission > 0

    def test_execute_market_sell(self):
        order = PaperOrder(side="sell", instrument="ES",
                           quantity=3, order_type="market")
        config = _make_config()
        updated, execution = execute_market_order(order, 6000.0, config)
        assert updated.status == "filled"
        assert updated.fill_price < 6000.0  # negative slippage
        assert updated.commission > 0

    def test_limit_buy_fills(self):
        order = PaperOrder(side="buy", instrument="ES",
                           quantity=2, order_type="limit", price=6000.0)
        config = _make_config()
        updated, execution = execute_limit_order(order, 6010.0, 5995.0, config)
        assert updated.status == "filled"
        assert execution is not None

    def test_limit_buy_no_fill(self):
        order = PaperOrder(side="buy", instrument="ES",
                           quantity=2, order_type="limit", price=6000.0)
        config = _make_config()
        updated, execution = execute_limit_order(order, 6010.0, 6005.0, config)
        assert execution is None

    def test_limit_sell_fills(self):
        order = PaperOrder(side="sell", instrument="ES",
                           quantity=2, order_type="limit", price=6100.0)
        config = _make_config()
        updated, execution = execute_limit_order(order, 6105.0, 6090.0, config)
        assert updated.status == "filled"

    def test_limit_sell_no_fill(self):
        order = PaperOrder(side="sell", instrument="ES",
                           quantity=2, order_type="limit", price=6100.0)
        config = _make_config()
        updated, execution = execute_limit_order(order, 6090.0, 6095.0, config)
        assert execution is None


# ─── Position Management ───────────────────────────────────

class TestPositions:
    """Position tracking, entry, exit, P&L."""

    def test_create_long_position(self):
        pos = update_position_after_fill(None, "buy", 3, 6000.0)
        assert pos.direction == "long"
        assert pos.quantity == 3
        assert pos.avg_entry_price == 6000.0
        assert pos.status == "open"

    def test_add_to_position(self):
        pos = update_position_after_fill(None, "buy", 2, 6000.0)
        pos = update_position_after_fill(pos, "buy", 1, 6100.0)
        assert pos.quantity == 3
        assert pos.avg_entry_price == pytest.approx(6033.33, abs=0.01)

    def test_close_position(self):
        pos = update_position_after_fill(None, "buy", 2, 6000.0)
        pos = update_position_after_fill(pos, "sell", 2, 6100.0)
        assert pos.status == "closed"
        assert pos.quantity == 0
        assert pos.realized_pnl == 200.0

    def test_partial_close(self):
        pos = update_position_after_fill(None, "buy", 4, 6000.0)
        pos = update_position_after_fill(pos, "sell", 1, 6100.0)
        assert pos.status == "open"
        assert pos.quantity == 3

    def test_unrealized_pnl_long(self):
        pos = PaperPosition(direction="long", quantity=2, avg_entry_price=6000.0,
                           current_price=6100.0, status="open")
        pnl = compute_unrealized_pnl(pos, 6100.0)
        assert pnl == 200.0

    def test_unrealized_pnl_short(self):
        pos = PaperPosition(direction="short", quantity=2, avg_entry_price=6100.0,
                           current_price=6000.0, status="open")
        pnl = compute_unrealized_pnl(pos, 6000.0)
        assert pnl == 200.0


# ─── Controller Order Flow ─────────────────────────────────

class TestControllerOrderFlow:
    """End-to-end order flow through the controller."""

    def test_place_and_process_market_order(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        controller.start_session(session.account_id)

        order = controller.place_order(
            session.account_id, "market", "buy", "ES", 2, price=None,
        )
        assert order.status == "pending"

        executions = controller.process_orders(session.account_id, 6000.0)
        assert len(executions) == 1
        assert executions[0].price > 6000.0  # with slippage
        assert session.balance < 100_000.0  # cost deducted

    def test_balance_after_buy(self):
        controller = PaperTradingController()
        config = _make_config(balance=100_000.0)
        session = controller.create_session(config)
        controller.start_session(session.account_id)
        controller.place_order(session.account_id, "market", "buy", "ES", 1)
        controller.process_orders(session.account_id, 6000.0)
        # Balance should be reduced by price + commission
        assert session.balance < 100_000.0

    def test_balance_after_sell_flat(self):
        """Buy then sell same qty at same price = net commission loss."""
        controller = PaperTradingController()
        config = _make_config(balance=100_000.0)
        session = controller.create_session(config)
        controller.start_session(session.account_id)

        controller.place_order(session.account_id, "market", "buy", "ES", 1, price=None)
        controller.process_orders(session.account_id, 6000.0)

        controller.place_order(session.account_id, "market", "sell", "ES", 1, price=None)
        controller.process_orders(session.account_id, 6000.0)

        # Net effect: 2 commissions paid, roughly balanced by slippage
        # Balance should be roughly initial minus ~5.00
        assert session.balance < 100_000.0

    def test_update_positions_mark_to_market(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        controller.start_session(session.account_id)
        controller.place_order(session.account_id, "market", "buy", "ES", 2)
        controller.process_orders(session.account_id, 6000.0)

        # Mark to market at higher price
        controller.update_positions(session.account_id, {"ES": 6100.0})
        assert session.unrealized_pnl > 0


# ─── State Export / Import ────────────────────────────────

class TestState:
    """State persistence and recovery."""

    def test_export_state(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        controller.start_session(session.account_id)
        controller.place_order(session.account_id, "market", "buy", "ES", 1)
        controller.process_orders(session.account_id, 6000.0)

        state = controller.export_state(session.account_id)
        assert state["status"] == "running"
        assert state["balance"] < 100_000.0
        assert len(state["orders"]) >= 1
        assert len(state["executions"]) >= 1

    def test_import_state(self):
        state = {
            "account_id": "test-123",
            "name": "Recovered", "balance": 95_000.0,
            "buying_power": 95_000.0, "initial_balance": 100_000.0,
            "realized_pnl": -5000.0, "unrealized_pnl": 0.0,
            "status": "stopped",
            "config": {"account_id": "test-123", "initial_balance": 100_000.0},
            "orders": [], "positions": [], "executions": [],
            "started_at": None, "stopped_at": None,
        }
        controller = PaperTradingController()
        session = controller.import_state(state)
        assert session.account_id == "test-123"
        assert session.balance == 95_000.0


# ─── Statistics ────────────────────────────────────────────

class TestStatistics:
    """Statistics calculation."""

    def test_empty_stats(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        stats = controller.get_statistics(session.account_id)
        assert stats["balance"] == 100_000.0
        assert stats["open_positions"] == 0

    def test_stats_with_trades(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        controller.start_session(session.account_id)
        # Two profitable trades
        for _ in range(2):
            controller.place_order(session.account_id, "market", "buy", "ES", 1)
            controller.process_orders(session.account_id, 6000.0)
            controller.place_order(session.account_id, "market", "sell", "ES", 1)
            controller.process_orders(session.account_id, 6100.0)
        stats = controller.get_statistics(session.account_id)
        assert stats["closed_positions"] > 0


# ─── Determinism ───────────────────────────────────────────

class TestDeterminism:
    """Deterministic calculations."""

    def test_slippage_deterministic(self):
        s1 = compute_slippage("market", "buy", 100.0, 2, 0.25)
        s2 = compute_slippage("market", "buy", 100.0, 2, 0.25)
        assert s1 == s2

    def test_commission_deterministic(self):
        c1 = compute_commission(5, 2.50)
        c2 = compute_commission(5, 2.50)
        assert c1 == c2


# ─── Serialization ─────────────────────────────────────────

class TestSerialization:
    """Dataclass serialization."""

    def test_session_to_dict(self):
        session = PaperSession(account_id="test", name="Test",
                               balance=100_000.0, status="running")
        d = session.to_dict()
        assert d["account_id"] == "test"
        assert d["balance"] == 100_000.0

    def test_order_to_dict(self):
        order = PaperOrder(side="buy", instrument="ES", quantity=2)
        d = order.to_dict()
        assert d["side"] == "buy"
        assert d["quantity"] == 2

    def test_position_to_dict(self):
        pos = PaperPosition(instrument="ES", direction="long",
                           quantity=3, avg_entry_price=6000.0)
        d = pos.to_dict()
        assert d["instrument"] == "ES"

    def test_execution_to_dict(self):
        exec_rec = PaperExecution(order_id="ord-1", instrument="ES",
                                  side="buy", quantity=2, price=6000.0)
        d = exec_rec.to_dict()
        assert d["price"] == 6000.0


# ─── Edge Cases ────────────────────────────────────────────

class TestEdgeCases:
    """Edge case handling."""

    def test_process_orders_when_paused(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        controller.start_session(session.account_id)
        controller.pause_session(session.account_id)
        controller.place_order(session.account_id, "market", "buy", "ES", 1)
        executions = controller.process_orders(session.account_id, 6000.0)
        assert len(executions) == 0  # No processing when paused

    def test_process_orders_when_stopped(self):
        controller = PaperTradingController()
        config = _make_config()
        session = controller.create_session(config)
        # Not started — status is "stopped"
        controller.place_order(session.account_id, "market", "buy", "ES", 1)
        executions = controller.process_orders(session.account_id, 6000.0)
        assert len(executions) == 0


# ─── API Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_paper_sessions_api():
    """Test /api/v1/paper/sessions endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/paper/sessions")
            assert response.status_code == 200
            data = response.json()
            assert "count" in data
    except ConnectionRefusedError:
        pytest.skip("Database not available")
