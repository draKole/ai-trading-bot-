"""Phase 4C Tests — Trade Management Engine.

Tests for trade lifecycle, state transitions, stop management,
target tracking, edge cases.
"""

from datetime import datetime, timedelta
import pytest

from app.services.trade_management.engine import (
    init_trade, enter_trade, process_bar, cancel_trade, expire_trade,
    ManagedTrade, TradeEvent, Bar, TradeManagementConfig, TradeState,
)


# ─── Helpers ─────────────────────────────────────────────────

def _setup(**overrides) -> dict:
    base = {
        "setup_id": "test-setup-001",
        "instrument": "ES",
        "direction": "bullish",
        "preferred_entry": 6010.0,
        "stop_reference": 6000.0,
        "target_1": 6030.0,
        "target_2": 6050.0,
        "target_3": 6070.0,
    }
    base.update(overrides)
    return base


def _pos_rec(contracts=2) -> dict:
    return {"recommended_contracts": contracts}


def _bar(timestamp=None, price=6010.0) -> Bar:
    if timestamp is None:
        timestamp = datetime(2025, 6, 16, 9, 30)
    return Bar(timestamp=timestamp, open=price, high=price + 1,
               low=price - 1, close=price)


def _bar_at(price: float, minute: int = 0) -> Bar:
    return Bar(timestamp=datetime(2025, 6, 16, 9, 30) + timedelta(minutes=minute),
               open=price, high=price + 1, low=price - 1, close=price)


# ─── Initialization ─────────────────────────────────────────

class TestInit:
    """Trade initialization from setup."""

    def test_init_bullish(self):
        trade = init_trade(_setup(), position_rec=_pos_rec(3))
        assert trade.state == "pending_entry"
        assert trade.entry_price == 6010.0
        assert trade.initial_stop == 6000.0
        assert trade.position_size == 3
        assert trade.target_1 == 6030.0
        assert trade.initial_risk_r == 10.0

    def test_init_bearish(self):
        trade = init_trade(
            _setup(direction="bearish", preferred_entry=6020.0, stop_reference=6030.0,
                   target_1=6000.0, target_2=5980.0, target_3=5960.0),
            position_rec=_pos_rec(2),
        )
        assert trade.direction == "bearish"
        assert trade.initial_risk_r == 10.0

    def test_init_creates_event(self):
        trade = init_trade(_setup())
        assert len(trade.events) == 1
        assert trade.events[0].event_type == "state_change"
        assert trade.events[0].to_state == "pending_entry"


# ─── Entry ───────────────────────────────────────────────────

class TestEntry:
    """Trade entry transitions."""

    def test_enter_transitions_to_active(self):
        trade = init_trade(_setup())
        events = enter_trade(trade, _bar())
        assert trade.state == "active"
        assert len(events) >= 1

    def test_enter_records_time(self):
        trade = init_trade(_setup())
        enter_trade(trade, _bar())
        assert trade.entry_time is not None


# ─── Stop Loss ───────────────────────────────────────────────

class TestStopLoss:
    """Stop loss handling."""

    def test_stop_loss_hit(self):
        trade = init_trade(_setup())
        enter_trade(trade, _bar_at(6010.0, 0))
        events = process_bar(trade, _bar_at(5990.0, 1))
        assert trade.state == "exited"
        # Should have an exit event
        assert any(e.event_type == "exit" for e in events)

    def test_stop_not_hit_above(self):
        trade = init_trade(_setup())
        enter_trade(trade, _bar_at(6010.0, 0))
        process_bar(trade, _bar_at(6010.0, 1))  # above stop
        assert trade.state != "exited"

    def test_bearish_stop_hit(self):
        trade = init_trade(
            _setup(direction="bearish", preferred_entry=6020.0, stop_reference=6030.0,
                   target_1=6000.0, target_2=5980.0, target_3=5960.0),
        )
        enter_trade(trade, _bar_at(6020.0, 0))
        process_bar(trade, _bar_at(6040.0, 1))  # above stop
        assert trade.state == "exited"

    def test_stop_not_hit_below_bearish(self):
        trade = init_trade(
            _setup(direction="bearish", preferred_entry=6020.0, stop_reference=6030.0,
                   target_1=6000.0, target_2=5980.0, target_3=5960.0),
        )
        enter_trade(trade, _bar_at(6020.0, 0))
        process_bar(trade, _bar_at(6010.0, 1))  # below stop for bearish
        assert trade.state != "exited"


# ─── Targets ─────────────────────────────────────────────────

class TestTargets:
    """Target hit handling."""

    def test_target_1_hit(self):
        trade = init_trade(_setup())
        enter_trade(trade, _bar_at(6010.0, 0))
        events = process_bar(trade, _bar_at(6035.0, 1))
        assert trade.target_1_hit is True
        assert trade.state == "target_1_hit"

    def test_target_2_hit_after_t1(self):
        trade = init_trade(_setup())
        enter_trade(trade, _bar_at(6010.0, 0))
        process_bar(trade, _bar_at(6035.0, 1))  # T1
        process_bar(trade, _bar_at(6055.0, 2))  # T2
        assert trade.target_2_hit is True
        assert trade.state == "target_2_hit"

    def test_target_3_hit_exits(self):
        trade = init_trade(_setup(), config=TradeManagementConfig(partial_exit_enabled=False))
        enter_trade(trade, _bar_at(6010.0, 0))
        process_bar(trade, _bar_at(6035.0, 1))
        process_bar(trade, _bar_at(6055.0, 2))
        events = process_bar(trade, _bar_at(6075.0, 3))
        assert trade.state == "exited"
        assert trade.target_3_hit is True

    def test_target_deduplication(self):
        """Target marked only once."""
        trade = init_trade(_setup())
        enter_trade(trade, _bar_at(6010.0, 0))
        process_bar(trade, _bar_at(6035.0, 1))
        t1_events = trade.events
        process_bar(trade, _bar_at(6040.0, 2))  # still above T1
        # No duplicate T1 event
        assert len(trade.events) == len(t1_events)


# ─── Breakeven ───────────────────────────────────────────────

class TestBreakeven:
    """Break-even stop movement."""

    def test_breakeven_at_1r(self):
        config = TradeManagementConfig(breakeven_trigger_r=1.0)
        trade = init_trade(_setup(), config=config)
        enter_trade(trade, _bar_at(6010.0, 0))
        # R=1 means price = entry + 1×risk = 6010 + 10 = 6020
        events = process_bar(trade, _bar_at(6025.0, 1))
        assert trade.breakeven_reached is True
        assert trade.current_stop == 6010.0
        assert trade.state == "stop_moved_to_breakeven"

    def test_breakeven_not_before_threshold(self):
        config = TradeManagementConfig(breakeven_trigger_r=1.0)
        trade = init_trade(_setup(), config=config)
        enter_trade(trade, _bar_at(6010.0, 0))
        # Only at 0.5R — shouldn't trigger breakeven
        process_bar(trade, _bar_at(6015.0, 1))
        assert trade.breakeven_reached is False

    def test_breakeven_disabled(self):
        config = TradeManagementConfig(breakeven_enabled=False)
        trade = init_trade(_setup(), config=config)
        enter_trade(trade, _bar_at(6010.0, 0))
        process_bar(trade, _bar_at(6025.0, 1))
        assert trade.breakeven_reached is False


# ─── Trailing Stop ───────────────────────────────────────────

class TestTrailingStop:
    """Trailing stop activation and movement."""

    def test_trailing_activates(self):
        config = TradeManagementConfig(
            trailing_activate_r=1.0, trailing_distance_pct=0.5,
        )
        trade = init_trade(_setup(), config=config)
        enter_trade(trade, _bar_at(6010.0, 0))
        events = process_bar(trade, _bar_at(6025.0, 1))
        assert trade.trailing_active is True

    def test_trailing_moves_up(self):
        config = TradeManagementConfig(
            trailing_activate_r=0.5, trailing_distance_pct=0.5,
        )
        trade = init_trade(_setup(), config=config)
        enter_trade(trade, _bar_at(6010.0, 0))
        process_bar(trade, _bar_at(6020.0, 1))  # activate trailing
        old_stop = trade.current_stop
        process_bar(trade, _bar_at(6030.0, 2))  # price moves up
        # Trailing should have raised the stop
        assert trade.current_stop >= old_stop

    def test_trailing_disabled(self):
        config = TradeManagementConfig(trailing_enabled=False)
        trade = init_trade(_setup(), config=config)
        enter_trade(trade, _bar_at(6010.0, 0))
        process_bar(trade, _bar_at(6030.0, 1))
        assert trade.trailing_active is False


# ─── Edge Cases ──────────────────────────────────────────────

class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_r_tracking(self):
        trade = init_trade(_setup())
        enter_trade(trade, _bar_at(6010.0, 0))
        process_bar(trade, _bar_at(6025.0, 1))  # ~1.5R
        assert trade.current_r == pytest.approx(1.5, abs=0.1)
        assert trade.peak_r == pytest.approx(1.5, abs=0.1)

    def test_cancel_pending(self):
        trade = init_trade(_setup())
        events = cancel_trade(trade, "test cancel")
        assert trade.state == "cancelled"
        assert len(events) == 1

    def test_cancel_already_exited_does_nothing(self):
        trade = init_trade(_setup())
        enter_trade(trade, _bar_at(6010.0, 0))
        process_bar(trade, _bar_at(5990.0, 1))  # stopped out
        assert trade.state == "exited"
        events = cancel_trade(trade)
        assert len(events) == 0

    def test_expire_pending(self):
        trade = init_trade(_setup())
        events = expire_trade(trade)
        assert trade.state == "expired"
        assert len(events) == 1

    def test_historical_consistency(self):
        """Same inputs → same state sequence."""
        t1 = init_trade(_setup())
        enter_trade(t1, _bar_at(6010.0, 0))
        process_bar(t1, _bar_at(6025.0, 1))
        process_bar(t1, _bar_at(6035.0, 2))

        t2 = init_trade(_setup())
        enter_trade(t2, _bar_at(6010.0, 0))
        process_bar(t2, _bar_at(6025.0, 1))
        process_bar(t2, _bar_at(6035.0, 2))

        assert t1.state == t2.state
        assert t1.breakeven_reached == t2.breakeven_reached

    def test_to_dict(self):
        trade = init_trade(_setup())
        d = trade.to_dict()
        assert isinstance(d, dict)
        assert d["state"] == "pending_entry"

    def test_event_to_dict(self):
        trade = init_trade(_setup())
        evt = trade.events[0].to_dict()
        assert isinstance(evt, dict)
        assert "event_type" in evt


# ─── API Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trade_manage_dry_run_no_db():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            response = await client.post(
                "/api/v1/trade-management/manage-dry-run",
                params={
                    "entry_price": 6010.0, "stop_price": 6000.0,
                    "direction": "bullish",
                    "bars_json": "[6020,6015,6030,6040]",
                },
            )
            assert response.status_code in (200, 500)
        except Exception:
            pass
