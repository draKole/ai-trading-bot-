"""Sprint 4: Paper Trading — API endpoints, order lifecycle, fill simulation, position P&L."""

from datetime import datetime, timezone

import pytest

from app.services.paper_trading.engine import (
    PaperTradingController, PaperTradingConfig,
    PaperSession, PaperOrder, PaperPosition, PaperExecution,
    execute_market_order, execute_limit_order,
    compute_slippage, compute_commission,
    update_position_after_fill, compute_unrealized_pnl,
    OrderType, OrderSide, OrderStatus, PositionStatus,
)


# ─── Slippage Tests ────────────────────────────────────────

class TestSlippage:
    def test_market_buy_slippage_positive(self):
        slip = compute_slippage("market", "buy", 100.0, 1, 0.25)
        assert slip == 0.25

    def test_market_sell_slippage_negative(self):
        slip = compute_slippage("market", "sell", 100.0, 1, 0.25)
        assert slip == -0.25

    def test_limit_order_no_slippage(self):
        slip = compute_slippage("limit", "buy", 100.0, 1, 0.25)
        assert slip == 0.0

    def test_multiple_ticks(self):
        slip = compute_slippage("market", "buy", 100.0, 4, 0.25)
        assert slip == 1.0


# ─── Commission Tests ──────────────────────────────────────

class TestCommission:
    def test_commission_calculation(self):
        comm = compute_commission(5, 2.50)
        assert comm == 12.50

    def test_single_contract(self):
        comm = compute_commission(1, 2.50)
        assert comm == 2.50

    def test_zero_quantity(self):
        comm = compute_commission(0, 2.50)
        assert comm == 0.0


# ─── Market Order Execution Tests ──────────────────────────

class TestMarketOrderExecution:
    def test_market_buy_fills_at_slipped_price(self):
        config = PaperTradingConfig(tick_size=0.25, default_slippage_ticks=1)
        order = PaperOrder(
            order_type="market", side="buy", instrument="ES",
            quantity=2, price=None,
        )
        updated, execution = execute_market_order(order, 5500.0, config)
        assert updated.status == "filled"
        assert updated.filled_qty == 2
        assert updated.fill_price == 5500.25  # current + slippage
        assert updated.slippage == 0.25
        assert updated.commission == 5.0  # 2 * 2.50
        assert execution.price == 5500.25
        assert execution.quantity == 2

    def test_market_sell_fills_at_slipped_price(self):
        config = PaperTradingConfig(tick_size=0.25, default_slippage_ticks=1)
        order = PaperOrder(
            order_type="market", side="sell", instrument="ES",
            quantity=1, price=None,
        )
        updated, execution = execute_market_order(order, 5500.0, config)
        assert updated.fill_price == 5499.75  # current - slippage
        assert updated.slippage == -0.25

    def test_market_order_status_transition(self):
        config = PaperTradingConfig()
        order = PaperOrder(order_type="market", side="buy", instrument="ES", quantity=1)
        assert order.status == "pending"
        updated, _ = execute_market_order(order, 100.0, config)
        assert updated.status == "filled"


# ─── Limit Order Execution Tests ───────────────────────────

class TestLimitOrderExecution:
    def test_limit_buy_fills_when_low_crosses(self):
        config = PaperTradingConfig()
        order = PaperOrder(
            order_type="limit", side="buy", instrument="ES",
            quantity=1, price=5495.0,
        )
        updated, execution = execute_limit_order(order, 5500.0, 5490.0, config)
        assert updated.status == "filled"
        assert updated.fill_price == 5495.0
        assert execution is not None

    def test_limit_buy_no_fill_when_price_not_crossed(self):
        config = PaperTradingConfig()
        order = PaperOrder(
            order_type="limit", side="buy", instrument="ES",
            quantity=1, price=5495.0,
        )
        updated, execution = execute_limit_order(order, 5500.0, 5500.0, config)
        assert updated.status == "pending"
        assert execution is None

    def test_limit_sell_fills_when_high_crosses(self):
        config = PaperTradingConfig()
        order = PaperOrder(
            order_type="limit", side="sell", instrument="ES",
            quantity=1, price=5510.0,
        )
        updated, execution = execute_limit_order(order, 5520.0, 5500.0, config)
        assert updated.status == "filled"
        assert updated.fill_price == 5510.0
        assert execution is not None

    def test_limit_sell_no_fill_when_price_not_crossed(self):
        config = PaperTradingConfig()
        order = PaperOrder(
            order_type="limit", side="sell", instrument="ES",
            quantity=1, price=5510.0,
        )
        updated, execution = execute_limit_order(order, 5500.0, 5500.0, config)
        assert updated.status == "pending"
        assert execution is None


# ─── Position Update Tests ─────────────────────────────────

class TestPositionUpdate:
    def test_create_new_long_position(self):
        pos = update_position_after_fill(None, "buy", 5, 5500.0)
        assert pos.direction == "long"
        assert pos.quantity == 5
        assert pos.avg_entry_price == 5500.0
        assert pos.status == "open"
        assert pos.unrealized_pnl == 0.0

    def test_create_new_short_position(self):
        pos = update_position_after_fill(None, "sell", 3, 5500.0)
        assert pos.direction == "short"
        assert pos.quantity == 3

    def test_add_to_existing_long(self):
        pos = PaperPosition(
            instrument="ES", direction="long", quantity=3,
            avg_entry_price=5500.0, current_price=5500.0,
            status="open",
        )
        updated = update_position_after_fill(pos, "buy", 2, 5510.0)
        assert updated.quantity == 5
        # avg entry: (3*5500 + 2*5510) / 5 = (16500 + 11020)/5 = 5504.0
        assert updated.avg_entry_price == 5504.0

    def test_close_long_position(self):
        pos = PaperPosition(
            instrument="ES", direction="long", quantity=5,
            avg_entry_price=5500.0, current_price=5500.0,
            status="open",
        )
        updated = update_position_after_fill(pos, "sell", 5, 5510.0)
        assert updated.quantity == 0
        assert updated.status == "closed"
        assert updated.realized_pnl == 50.0  # (5510-5500)*5 = 50

    def test_partial_close_long(self):
        pos = PaperPosition(
            instrument="ES", direction="long", quantity=10,
            avg_entry_price=5500.0, current_price=5500.0,
            status="open",
        )
        updated = update_position_after_fill(pos, "sell", 3, 5510.0)
        assert updated.quantity == 7
        assert updated.status == "open"
        assert updated.avg_entry_price == 5500.0


# ─── Unrealized P&L Tests ──────────────────────────────────

class TestUnrealizedPnL:
    def test_long_unrealized(self):
        pos = PaperPosition(
            instrument="ES", direction="long", quantity=5,
            avg_entry_price=5500.0,
        )
        pnl = compute_unrealized_pnl(pos, 5510.0)
        assert pnl == 50.0  # (5510-5500) * 5

    def test_short_unrealized(self):
        pos = PaperPosition(
            instrument="ES", direction="short", quantity=5,
            avg_entry_price=5500.0,
        )
        pnl = compute_unrealized_pnl(pos, 5490.0)
        assert pnl == 50.0  # (5500-5490) * 5

    def test_zero_quantity_no_pnl(self):
        pos = PaperPosition(
            instrument="ES", direction="long", quantity=0,
            avg_entry_price=5500.0,
        )
        assert compute_unrealized_pnl(pos, 5510.0) == 0.0


# ─── Controller Tests ──────────────────────────────────────

class TestController:
    def test_create_session(self):
        ctrl = PaperTradingController()
        sess = ctrl.create_session()
        assert sess.status == "stopped"
        assert sess.balance == 100_000.0
        assert sess.initial_balance == 100_000.0

    def test_start_session(self):
        ctrl = PaperTradingController()
        config = PaperTradingConfig(
            account_id="test-001", name="Test", initial_balance=50000.0,
        )
        ctrl.create_session(config)
        sess = ctrl.start_session("test-001")
        assert sess.status == "running"
        assert sess.started_at is not None

    def test_pause_resume_stop(self):
        ctrl = PaperTradingController()
        config = PaperTradingConfig(account_id="test-002")
        ctrl.create_session(config)
        ctrl.start_session("test-002")

        ctrl.pause_session("test-002")
        assert ctrl.get_session("test-002").status == "paused"

        ctrl.resume_session("test-002")
        assert ctrl.get_session("test-002").status == "running"

        ctrl.stop_session("test-002")
        assert ctrl.get_session("test-002").status == "stopped"
        assert ctrl.get_session("test-002").stopped_at is not None

    def test_place_order_adds_to_session(self):
        ctrl = PaperTradingController()
        config = PaperTradingConfig(account_id="test-003")
        ctrl.create_session(config)
        ctrl.start_session("test-003")

        order = ctrl.place_order(
            "test-003", "market", "buy", "ES", 2, price=None,
        )
        assert order.side == "buy"
        assert order.instrument == "ES"
        assert order.quantity == 2
        assert order.status == "pending"

    def test_process_market_orders(self):
        ctrl = PaperTradingController()
        config = PaperTradingConfig(account_id="test-004")
        ctrl.create_session(config)
        ctrl.start_session("test-004")

        ctrl.place_order("test-004", "market", "buy", "ES", 1, price=None)
        executions = ctrl.process_orders("test-004", 5500.0)
        assert len(executions) == 1
        assert executions[0].side == "buy"
        assert executions[0].price > 5500.0  # slippage

    def test_process_limit_order_fills_on_cross(self):
        ctrl = PaperTradingController()
        config = PaperTradingConfig(account_id="test-005")
        ctrl.create_session(config)
        ctrl.start_session("test-005")

        ctrl.place_order("test-005", "limit", "buy", "ES", 1, price=5490.0)
        executions = ctrl.process_orders("test-005", 5500.0, 5500.0, 5485.0)
        assert len(executions) == 1
        assert executions[0].price == 5490.0

    def test_balances_update_after_fill(self):
        ctrl = PaperTradingController()
        config = PaperTradingConfig(account_id="test-006")
        ctrl.create_session(config)
        ctrl.start_session("test-006")

        ctrl.place_order("test-006", "market", "buy", "ES", 1, price=None)
        ctrl.process_orders("test-006", 5500.0)

        session = ctrl.get_session("test-006")
        # Balance should decrease by fill price + commission
        assert session.balance < session.initial_balance

    def test_statistics(self):
        ctrl = PaperTradingController()
        config = PaperTradingConfig(account_id="test-007")
        ctrl.create_session(config)
        ctrl.start_session("test-007")

        stats = ctrl.get_statistics("test-007")
        assert stats["balance"] == 100_000.0
        assert stats["realized_pnl"] == 0.0
        assert stats["open_positions"] == 0
        assert stats["total_orders"] == 0


# ─── Enums Tests ───────────────────────────────────────────

class TestEnums:
    def test_order_types(self):
        assert OrderType.MARKET == "market"
        assert OrderType.LIMIT == "limit"
        assert OrderType.STOP == "stop"
        assert OrderType.STOP_LIMIT == "stop_limit"

    def test_order_sides(self):
        assert OrderSide.BUY == "buy"
        assert OrderSide.SELL == "sell"

    def test_order_statuses(self):
        assert OrderStatus.PENDING == "pending"
        assert OrderStatus.FILLED == "filled"
        assert OrderStatus.CANCELLED == "cancelled"
        assert OrderStatus.REJECTED == "rejected"


# ─── Config Tests ──────────────────────────────────────────

class TestConfig:
    def test_default_config(self):
        cfg = PaperTradingConfig()
        assert cfg.initial_balance == 100_000.0
        assert cfg.default_slippage_ticks == 1
        assert cfg.tick_size == 0.25
        assert cfg.commission_per_contract == 2.50

    def test_config_to_dict(self):
        cfg = PaperTradingConfig(account_id="abc", name="Test")
        d = cfg.to_dict()
        assert d["account_id"] == "abc"
        assert d["name"] == "Test"
        assert "initial_balance" in d

    def test_config_from_dict(self):
        d = {"account_id": "xyz", "name": "FromDict", "initial_balance": 50000.0}
        cfg = PaperTradingConfig.from_dict(d)
        assert cfg.account_id == "xyz"
        assert cfg.initial_balance == 50000.0
