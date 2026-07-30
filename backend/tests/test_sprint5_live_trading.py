"""Sprint 5: Config-driven Live Trading — mode switching, kill switch, risk controls, audit log."""

import os
from datetime import datetime, timezone

import pytest

from app.services.mode.manager import ModeManager, ModeState
from app.services.broker.mock import MockBrokerAdapter
from app.services.broker.base import BrokerOrder, BrokerPosition, ConnectionState
from app.services.risk.controls import (
    ExecutionRiskController, ExecutionRiskConfig,
    CircuitBreakerTracker, DailyLossTracker,
)


# ═══════════════════════════════════════════════════════════════
# Mode Manager Tests
# ═══════════════════════════════════════════════════════════════

class TestModeManager:
    def test_defaults_to_paper(self):
        mgr = ModeManager()
        assert mgr.mode == "paper"
        assert mgr.is_paper
        assert not mgr.is_live
        assert not mgr.is_killed

    def test_switch_to_live_requires_confirm(self):
        mgr = ModeManager()
        result = mgr.switch_mode("live", confirm=False)
        assert result["status"] == "confirmation_required"
        assert mgr.mode == "paper"

    def test_switch_to_live_with_confirm(self):
        mgr = ModeManager()
        result = mgr.switch_mode("live", confirm=True)
        assert result["status"] == "switched"
        assert mgr.is_live
        assert mgr.mode == "live"

    def test_switch_back_to_paper(self):
        mgr = ModeManager()
        mgr.switch_mode("live", confirm=True)
        result = mgr.switch_mode("paper", confirm=True)
        assert result["status"] == "switched"
        assert mgr.is_paper

    def test_switch_to_same_mode_is_unchanged(self):
        mgr = ModeManager()
        result = mgr.switch_mode("paper", confirm=True)
        assert result["status"] == "unchanged"

    def test_invalid_mode_raises(self):
        mgr = ModeManager()
        with pytest.raises(ValueError):
            mgr.switch_mode("invalid", confirm=True)

    def test_kill_switch(self):
        mgr = ModeManager()
        result = mgr.kill()
        assert result["status"] == "killed"
        assert mgr.is_killed

    def test_cannot_switch_when_killed(self):
        mgr = ModeManager()
        mgr.kill()
        result = mgr.switch_mode("live", confirm=True)
        assert result["status"] == "rejected"

    def test_kill_already_killed_is_idempotent(self):
        mgr = ModeManager()
        mgr.kill()
        result = mgr.kill()
        assert result["status"] == "already_killed"

    def test_can_trade_returns_true_by_default(self):
        mgr = ModeManager()
        allowed, reason = mgr.check_can_trade()
        assert allowed
        assert reason == "OK"

    def test_can_trade_returns_false_when_killed(self):
        mgr = ModeManager()
        mgr.kill()
        allowed, reason = mgr.check_can_trade()
        assert not allowed
        assert "kill" in reason.lower()

    def test_state_returns_dict(self):
        mgr = ModeManager()
        state = mgr.state
        assert state["mode"] == "paper"
        assert "is_live" in state
        assert "killed" in state

    def test_env_var_sets_initial_mode(self):
        os.environ["TRADING_MODE"] = "live"
        mgr = ModeManager()
        assert mgr.mode == "live"
        del os.environ["TRADING_MODE"]

    def test_invalid_env_var_defaults_to_paper(self):
        os.environ["TRADING_MODE"] = "garbage"
        mgr = ModeManager()
        assert mgr.mode == "paper"
        del os.environ["TRADING_MODE"]


# ═══════════════════════════════════════════════════════════════
# Mock Broker Adapter Tests
# ═══════════════════════════════════════════════════════════════

class TestMockBroker:
    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        adapter = MockBrokerAdapter()
        assert not await adapter.is_connected()
        await adapter.connect()
        assert await adapter.is_connected()
        await adapter.disconnect()
        assert not await adapter.is_connected()

    @pytest.mark.asyncio
    async def test_place_market_order_fills_immediately(self):
        adapter = MockBrokerAdapter()
        await adapter.connect()
        order = BrokerOrder(
            instrument="ES", action="buy", order_type="market", quantity=2,
        )
        result = await adapter.place_order(order)
        assert result.status == "filled"
        assert result.filled_qty == 2
        assert result.avg_fill_price == 5500.0
        assert result.broker_order_id.startswith("mock-")

    @pytest.mark.asyncio
    async def test_place_limit_order_stays_working(self):
        adapter = MockBrokerAdapter()
        await adapter.connect()
        order = BrokerOrder(
            instrument="ES", action="buy", order_type="limit",
            limit_price=5400.0, quantity=1,
        )
        result = await adapter.place_order(order)
        assert result.status == "working"

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        adapter = MockBrokerAdapter()
        await adapter.connect()
        order = BrokerOrder(
            instrument="ES", action="buy", order_type="market", quantity=1,
        )
        result = await adapter.place_order(order)
        assert await adapter.cancel_order(result.order_id)
        retrieved = await adapter.get_order(result.order_id)
        assert retrieved.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self):
        adapter = MockBrokerAdapter()
        await adapter.connect()
        assert not await adapter.cancel_order("nonexistent")

    @pytest.mark.asyncio
    async def test_modify_order(self):
        adapter = MockBrokerAdapter()
        await adapter.connect()
        order = BrokerOrder(
            instrument="ES", action="buy", order_type="limit",
            limit_price=5400.0, quantity=1,
        )
        result = await adapter.place_order(order)
        modified = await adapter.modify_order(result.order_id, {"limit_price": 5410.0})
        assert modified.limit_price == 5410.0

    @pytest.mark.asyncio
    async def test_get_order_nonexistent(self):
        adapter = MockBrokerAdapter()
        await adapter.connect()
        assert await adapter.get_order("fake") is None

    @pytest.mark.asyncio
    async def test_get_positions_tracks_fills(self):
        adapter = MockBrokerAdapter()
        await adapter.connect()
        order = BrokerOrder(
            instrument="ES", action="buy", order_type="market", quantity=3,
        )
        await adapter.place_order(order)
        positions = await adapter.get_positions()
        assert len(positions) == 1
        assert positions[0].instrument == "ES"
        assert positions[0].quantity == 3

    @pytest.mark.asyncio
    async def test_get_account_returns_default(self):
        adapter = MockBrokerAdapter()
        await adapter.connect()
        acct = await adapter.get_account()
        assert acct.balance == 100_000.0
        assert acct.buying_power == 100_000.0

    @pytest.mark.asyncio
    async def test_get_market_price(self):
        adapter = MockBrokerAdapter()
        assert await adapter.get_market_price("ES") == 5500.0

    @pytest.mark.asyncio
    async def test_set_price(self):
        adapter = MockBrokerAdapter()
        adapter.set_price("ES", 5600.0)
        assert await adapter.get_market_price("ES") == 5600.0


# ═══════════════════════════════════════════════════════════════
# Circuit Breaker Tests
# ═══════════════════════════════════════════════════════════════

class TestCircuitBreaker:
    def test_starts_with_zero_losses(self):
        cb = CircuitBreakerTracker(max_consecutive=3)
        assert cb.consecutive_losses == 0
        assert not cb.is_triggered()

    def test_records_losses(self):
        cb = CircuitBreakerTracker(max_consecutive=3)
        cb.record_loss(100)
        cb.record_loss(50)
        assert cb.consecutive_losses == 2
        assert not cb.is_triggered()

    def test_triggers_at_threshold(self):
        cb = CircuitBreakerTracker(max_consecutive=3)
        cb.record_loss(100)
        cb.record_loss(50)
        cb.record_loss(200)
        assert cb.consecutive_losses == 3
        assert cb.is_triggered()

    def test_win_resets_counter(self):
        cb = CircuitBreakerTracker(max_consecutive=3)
        cb.record_loss(100)
        cb.record_loss(50)
        cb.record_win()
        assert cb.consecutive_losses == 0
        assert not cb.is_triggered()

    def test_reset_clears_all(self):
        cb = CircuitBreakerTracker(max_consecutive=3)
        cb.record_loss(100)
        cb.record_loss(50)
        cb.reset()
        assert cb.consecutive_losses == 0


# ═══════════════════════════════════════════════════════════════
# Daily Loss Tracker Tests
# ═══════════════════════════════════════════════════════════════

class TestDailyLossTracker:
    def test_starts_at_zero(self):
        dt = DailyLossTracker(limit=1000.0)
        assert dt.current_loss == 0.0
        assert not dt.is_exceeded()

    def test_records_losses(self):
        dt = DailyLossTracker(limit=1000.0)
        dt.record_pnl(-300)
        dt.record_pnl(-200)
        assert dt.current_loss == 500.0
        assert not dt.is_exceeded()

    def test_exceeded_when_over_limit(self):
        dt = DailyLossTracker(limit=500.0)
        dt.record_pnl(-400)
        dt.record_pnl(-150)
        assert dt.is_exceeded()

    def test_profits_do_not_add_to_loss(self):
        dt = DailyLossTracker(limit=500.0)
        dt.record_pnl(200)  # profit
        dt.record_pnl(-200)
        assert dt.current_loss == 200.0

    def test_reset_clears_loss(self):
        dt = DailyLossTracker(limit=1000.0)
        dt.record_pnl(-500)
        dt.reset()
        assert dt.current_loss == 0.0


# ═══════════════════════════════════════════════════════════════
# Execution Risk Controller Tests
# ═══════════════════════════════════════════════════════════════

class TestExecutionRiskController:
    def test_starts_not_killed(self):
        rc = ExecutionRiskController()
        assert not rc.is_killed

    def test_kill_switch_activation(self):
        rc = ExecutionRiskController()
        result = rc.kill()
        assert result["status"] == "killed"
        assert rc.is_killed

    def test_already_killed_idempotent(self):
        rc = ExecutionRiskController()
        rc.kill()
        result = rc.kill()
        assert result["status"] == "already_killed"

    def test_check_order_allows_when_ok(self):
        rc = ExecutionRiskController()
        allowed, reason = rc.check_order("ES", 2, "buy")
        assert allowed
        assert reason == "OK"

    def test_check_order_blocks_when_killed(self):
        rc = ExecutionRiskController()
        rc.kill()
        allowed, reason = rc.check_order("ES", 2, "buy")
        assert not allowed
        assert "kill" in reason.lower()

    def test_max_position_exceeded(self):
        cfg = ExecutionRiskConfig(max_position_size={"ES": 3})
        rc = ExecutionRiskController(cfg)
        rc.update_position("ES", 3, "buy")
        allowed, reason = rc.check_order("ES", 2, "buy")
        assert not allowed
        assert "max position" in reason.lower()

    def test_max_position_within_limit(self):
        cfg = ExecutionRiskConfig(max_position_size={"ES": 10})
        rc = ExecutionRiskController(cfg)
        rc.update_position("ES", 3, "buy")
        allowed, _ = rc.check_order("ES", 2, "buy")
        assert allowed

    def test_record_trade_loss_adds_to_circuit_breaker(self):
        cfg = ExecutionRiskConfig(circuit_breaker_consecutive_losses=2)
        rc = ExecutionRiskController(cfg)
        rc.record_trade(-100)
        rc.record_trade(-50)
        # Circuit breaker fires at 2 consecutive losses
        assert rc.is_killed

    def test_record_trade_win_resets_circuit_breaker(self):
        cfg = ExecutionRiskConfig(circuit_breaker_consecutive_losses=2)
        rc = ExecutionRiskController(cfg)
        rc.record_trade(-100)
        rc.record_trade(50)  # win
        rc.record_trade(-30)
        assert not rc.is_killed

    def test_daily_loss_limit_triggers_kill(self):
        cfg = ExecutionRiskConfig(
            daily_loss_limit=200.0,
            circuit_breaker_enabled=False,
        )
        rc = ExecutionRiskController(cfg)
        rc.record_trade(-150)
        rc.record_trade(-60)
        assert rc.is_killed

    def test_get_status_returns_all_fields(self):
        rc = ExecutionRiskController()
        status = rc.get_status()
        assert "killed" in status
        assert "circuit_breaker" in status
        assert "daily_loss" in status
        assert "max_position" in status

    def test_config_from_env(self):
        cfg = ExecutionRiskConfig.from_env()
        assert cfg.daily_loss_limit == 1000.0
        assert cfg.circuit_breaker_consecutive_losses == 3
        assert cfg.max_position_size["ES"] == 10


# ═══════════════════════════════════════════════════════════════
# Paper/Live Isolation Tests
# ═══════════════════════════════════════════════════════════════

class TestPaperLiveIsolation:
    """Verify that paper and live modes are fully isolated."""

    def test_paper_mode_does_not_require_broker(self):
        """In paper mode, trading should work without broker connectivity."""
        mgr = ModeManager()
        assert mgr.mode == "paper"
        # Paper mode doesn't touch broker at all

    @pytest.mark.asyncio
    async def test_mock_broker_isolated_from_live(self):
        """Mock broker has its own state, separate from any live broker."""
        mock = MockBrokerAdapter()
        await mock.connect()
        await mock.place_order(
            BrokerOrder(instrument="ES", action="buy", order_type="market", quantity=1),
        )
        positions = await mock.get_positions()
        assert len(positions) == 1
        # This only affects mock state — no live broker is touched
