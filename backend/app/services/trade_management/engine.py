"""Trade Management Engine — lifecycle state machine for active trades.

Consumes Trade Setup + Risk Report + Position Recommendation + market bars
to manage trade state: stop movements, target tracking, exit rules.

Advisory only — no broker communication, no execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4


# ─── Enums ──────────────────────────────────────────────────

class TradeState(str, Enum):
    PENDING_ENTRY = "pending_entry"
    ENTERED = "entered"
    PARTIALLY_FILLED = "partially_filled"
    ACTIVE = "active"
    TARGET_1_HIT = "target_1_hit"
    TARGET_2_HIT = "target_2_hit"
    TARGET_3_HIT = "target_3_hit"
    STOP_MOVED_TO_BREAKEVEN = "stop_moved_to_breakeven"
    TRAILING_STOP_ACTIVE = "trailing_stop_active"
    EXITED = "exited"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ExitReason(str, Enum):
    TARGET_1 = "target_1"
    TARGET_2 = "target_2"
    TARGET_3 = "target_3"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    BREAKEVEN_STOP = "breakeven_stop"
    TIME_EXIT = "time_exit"
    SESSION_CLOSE = "session_close"
    MANUAL = "manual"
    EXPIRED = "expired"


# ─── Management Config ──────────────────────────────────────

@dataclass
class TradeManagementConfig:
    """Configurable trade management rules — no hard-coded values."""

    # Break-even
    breakeven_trigger_r: float = 1.0    # Move stop to breakeven at 1R profit
    breakeven_enabled: bool = True

    # Trailing stop
    trailing_activate_r: float = 1.5    # Activate trailing at 1.5R
    trailing_distance_pct: float = 0.5  # Trail by 0.5% of price
    trailing_enabled: bool = True

    # Partial profit
    partial_exit_pct: float = 0.33      # Close 33% at each target
    partial_exit_enabled: bool = False

    # Time exits
    max_trade_duration_minutes: int | None = None  # No limit
    time_exit_enabled: bool = False

    # Session close
    exit_on_session_close: bool = False
    session_close_buffer_minutes: int = 5

    # Gap handling
    gap_skip_stops: bool = True  # Don't trigger stops on gap opens

    # Minimum profit lock
    min_profit_lock_r: float = 0.0  # Lock in profit above this R

    def to_dict(self) -> dict:
        return {
            "breakeven_trigger_r": self.breakeven_trigger_r,
            "breakeven_enabled": self.breakeven_enabled,
            "trailing_activate_r": self.trailing_activate_r,
            "trailing_distance_pct": self.trailing_distance_pct,
            "trailing_enabled": self.trailing_enabled,
            "partial_exit_pct": self.partial_exit_pct,
            "partial_exit_enabled": self.partial_exit_enabled,
            "max_trade_duration_minutes": self.max_trade_duration_minutes,
            "time_exit_enabled": self.time_exit_enabled,
            "exit_on_session_close": self.exit_on_session_close,
            "session_close_buffer_minutes": self.session_close_buffer_minutes,
            "gap_skip_stops": self.gap_skip_stops,
            "min_profit_lock_r": self.min_profit_lock_r,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TradeManagementConfig:
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


# ─── Bar Data ────────────────────────────────────────────────

@dataclass
class Bar:
    """A single price bar for management evaluation."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float


# ─── Trade Event ────────────────────────────────────────────

@dataclass
class TradeEvent:
    """Immutable record of a state transition or management action."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    trade_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_type: str = ""  # state_change, stop_update, target_hit, exit
    from_state: str = ""
    to_state: str = ""
    detail: str = ""
    price: float | None = None
    r_multiple: float = 0.0
    unrealized_pnl: float = 0.0
    position_remaining_pct: float = 100.0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "trade_id": self.trade_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "detail": self.detail,
            "price": self.price,
            "r_multiple": round(self.r_multiple, 4),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "position_remaining_pct": self.position_remaining_pct,
        }


# ─── Managed Trade ──────────────────────────────────────────

@dataclass
class ManagedTrade:
    """Stateful representation of a managed trade."""
    trade_id: str = field(default_factory=lambda: str(uuid4()))
    setup_id: str = ""
    instrument: str = ""
    direction: str = ""

    # Entry
    entry_price: float = 0.0
    initial_stop: float = 0.0
    current_stop: float = 0.0
    position_size: int = 0
    position_remaining: int = 0

    # Targets
    target_1: float | None = None
    target_2: float | None = None
    target_3: float | None = None
    target_1_hit: bool = False
    target_2_hit: bool = False
    target_3_hit: bool = False

    # State
    state: str = "pending_entry"
    entry_time: datetime | None = None
    last_update: datetime = field(default_factory=datetime.utcnow)

    # Metrics
    initial_risk_r: float = 0.0  # 1R in price points
    peak_r: float = 0.0          # MFE in R
    max_adverse_r: float = 0.0   # MAE in R
    current_r: float = 0.0       # Current R-multiple

    # Flags
    breakeven_reached: bool = False
    trailing_active: bool = False
    highest_price: float = 0.0   # For trailing stop (long)
    lowest_price: float = 0.0    # For trailing stop (short)

    # Config
    config: TradeManagementConfig = field(default_factory=TradeManagementConfig)

    # Events
    events: list[TradeEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "setup_id": self.setup_id,
            "instrument": self.instrument,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "initial_stop": self.initial_stop,
            "current_stop": self.current_stop,
            "position_size": self.position_size,
            "position_remaining": self.position_remaining,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "target_3": self.target_3,
            "target_1_hit": self.target_1_hit,
            "target_2_hit": self.target_2_hit,
            "target_3_hit": self.target_3_hit,
            "state": self.state,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "initial_risk_r": round(self.initial_risk_r, 4),
            "peak_r": round(self.peak_r, 4),
            "max_adverse_r": round(self.max_adverse_r, 4),
            "current_r": round(self.current_r, 4),
            "breakeven_reached": self.breakeven_reached,
            "trailing_active": self.trailing_active,
        }


# ─── Trade Manager ──────────────────────────────────────────

def _add_event(trade: ManagedTrade, event_type: str, from_state: str,
               to_state: str, detail: str = "", price: float | None = None) -> TradeEvent:
    """Create and append a trade event."""
    event = TradeEvent(
        trade_id=trade.trade_id,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        detail=detail,
        price=price,
        r_multiple=trade.current_r,
        position_remaining_pct=(trade.position_remaining / max(trade.position_size, 1)) * 100,
    )
    trade.events.append(event)
    return event


def init_trade(
    setup: dict,
    risk_report: dict | None = None,
    position_rec: dict | None = None,
    config: TradeManagementConfig | None = None,
) -> ManagedTrade:
    """Initialize a managed trade from setup + position recommendation."""
    if config is None:
        config = TradeManagementConfig()

    entry = float(setup.get("preferred_entry", 0) or
                  ((setup.get("entry_zone_low", 0) or 0) +
                   (setup.get("entry_zone_high", 0) or 0)) / 2)
    stop = float(setup.get("stop_reference", 0) or 0)
    direction = str(setup.get("direction", "bullish")).lower()

    if direction == "bullish":
        risk_r = entry - stop if stop > 0 else 1.0
    else:
        risk_r = stop - entry if stop > 0 else 1.0

    t1 = float(setup.get("target_1", 0) or 0)
    t2 = float(setup.get("target_2", 0) or 0)
    t3 = float(setup.get("target_3", 0) or 0)

    contracts = 0
    if position_rec:
        contracts = int(position_rec.get("recommended_contracts", 0) or 0)

    trade = ManagedTrade(
        setup_id=str(setup.get("setup_id", "")),
        instrument=str(setup.get("instrument", "")),
        direction=direction,
        entry_price=entry,
        initial_stop=stop,
        current_stop=stop,
        position_size=contracts,
        position_remaining=contracts,
        target_1=t1 if t1 > 0 else None,
        target_2=t2 if t2 > 0 else None,
        target_3=t3 if t3 > 0 else None,
        state="pending_entry",
        initial_risk_r=max(risk_r, 0.01),
        config=config,
    )
    _add_event(trade, "state_change", "", "pending_entry", "Trade initialized")
    return trade


def enter_trade(trade: ManagedTrade, bar: Bar | None = None) -> list[TradeEvent]:
    """Transition from pending_entry → entered/active."""
    if trade.state != "pending_entry":
        return []

    events: list[TradeEvent] = []

    trade.state = "entered"
    trade.entry_time = bar.timestamp if bar else datetime.utcnow()

    if trade.direction == "bullish":
        trade.highest_price = trade.entry_price
        trade.lowest_price = trade.entry_price
    else:
        trade.highest_price = trade.entry_price
        trade.lowest_price = trade.entry_price

    trade.state = "active"
    evt = _add_event(trade, "state_change", "pending_entry", "active",
                     f"Entered at {trade.entry_price}")
    events.append(evt)
    return events


def process_bar(trade: ManagedTrade, bar: Bar) -> list[TradeEvent]:
    """Process a single price bar against the managed trade.

    Evaluates: stop loss, targets, breakeven, trailing stop, time/session exits.
    Returns list of events generated by this bar.
    """
    if trade.state in ("exited", "cancelled", "expired"):
        return []

    events: list[TradeEvent] = []

    # Ensure we're active (auto-enter if needed)
    if trade.state == "pending_entry":
        events.extend(enter_trade(trade, bar))
    if trade.state not in ("active", "partially_filled", "target_1_hit",
                           "target_2_hit", "target_3_hit",
                           "stop_moved_to_breakeven", "trailing_stop_active"):
        return events

    # Track extremes
    if trade.direction == "bullish":
        trade.highest_price = max(trade.highest_price, bar.high)
        trade.lowest_price = min(trade.lowest_price, bar.low)
    else:
        trade.highest_price = max(trade.highest_price, bar.high)
        trade.lowest_price = min(trade.lowest_price, bar.low)

    # Update current R
    if trade.direction == "bullish":
        profit_pts = bar.close - trade.entry_price
    else:
        profit_pts = trade.entry_price - bar.close

    trade.current_r = profit_pts / trade.initial_risk_r if trade.initial_risk_r > 0 else 0
    trade.peak_r = max(trade.peak_r, trade.current_r)
    trade.max_adverse_r = min(trade.max_adverse_r, trade.current_r)

    # ── Check Stop Loss ──
    stop_hit = False
    if trade.direction == "bullish":
        if bar.low <= trade.current_stop:
            stop_hit = True
    else:
        if bar.high >= trade.current_stop:
            stop_hit = True

    if stop_hit:
        trade.state = "exited"
        evt = _add_event(trade, "exit", trade.state, "exited",
                         f"Stop loss hit at {trade.current_stop}",
                         price=trade.current_stop)
        events.append(evt)
        return events

    # ── Breakeven (before targets so targets can override) ──
    if (trade.config.breakeven_enabled and not trade.breakeven_reached
            and trade.current_r >= trade.config.breakeven_trigger_r
            and trade.current_stop != trade.entry_price):
        old_stop = trade.current_stop
        trade.current_stop = trade.entry_price
        trade.breakeven_reached = True
        old_state = trade.state
        trade.state = "stop_moved_to_breakeven"
        evt = _add_event(trade, "stop_update", old_state, "stop_moved_to_breakeven",
                         f"Stop moved to breakeven ({trade.entry_price}) from {old_stop}",
                         price=trade.entry_price)
        events.append(evt)

    # ── Trailing Stop (before targets) ──
    if (trade.config.trailing_enabled and trade.current_r >= trade.config.trailing_activate_r):
        if not trade.trailing_active:
            trade.trailing_active = True
            if trade.state not in ("stop_moved_to_breakeven", "trailing_stop_active",
                                    "target_1_hit", "target_2_hit", "target_3_hit"):
                old_state = trade.state
                trade.state = "trailing_stop_active"
                _add_event(trade, "trailing_activate",
                           old_state, "trailing_stop_active",
                           f"Trailing stop activated at R={trade.current_r:.2f}")
            else:
                _add_event(trade, "trailing_activate",
                           trade.state, trade.state,
                           f"Trailing stop activated at R={trade.current_r:.2f}")

        # Calculate trail
        trail_dist = trade.entry_price * (trade.config.trailing_distance_pct / 100)
        if trade.direction == "bullish":
            new_stop = trade.highest_price - trail_dist
            if new_stop > trade.current_stop:
                old = trade.current_stop
                trade.current_stop = new_stop
                _add_event(trade, "stop_update", trade.state,
                           trade.state,
                           f"Trailing stop: {old} → {new_stop}", price=new_stop)
        else:
            new_stop = trade.lowest_price + trail_dist
            if new_stop < trade.current_stop:
                old = trade.current_stop
                trade.current_stop = new_stop
                _add_event(trade, "stop_update", trade.state,
                           trade.state,
                           f"Trailing stop: {old} → {new_stop}", price=new_stop)

    # ── Check Targets (last so they take priority over breakeven/trailing) ──
    targets = [
        (trade.target_1, "target_1_hit", "Target 1", trade.target_1_hit),
        (trade.target_2, "target_2_hit", "Target 2", trade.target_2_hit),
        (trade.target_3, "target_3_hit", "Target 3", trade.target_3_hit),
    ]

    for tgt, state_name, label, already_hit in targets:
        if tgt is None or already_hit:
            continue
        hit = False
        if trade.direction == "bullish":
            hit = bar.high >= tgt
        else:
            hit = bar.low <= tgt

        if hit:
            if state_name == "target_1_hit":
                trade.target_1_hit = True
            elif state_name == "target_2_hit":
                trade.target_2_hit = True
            elif state_name == "target_3_hit":
                trade.target_3_hit = True

            old_state = trade.state
            trade.state = state_name
            evt = _add_event(trade, "target_hit", old_state, state_name,
                             f"{label} hit at {tgt}", price=tgt)
            events.append(evt)

            # Partial exit
            if trade.config.partial_exit_enabled:
                exit_qty = int(trade.position_size * trade.config.partial_exit_pct)
                trade.position_remaining = max(0, trade.position_remaining - exit_qty)
                _add_event(trade, "partial_exit", state_name, state_name,
                           f"Partial exit: {exit_qty} contracts at {tgt}", price=tgt)

            if state_name == "target_3_hit" and not trade.config.partial_exit_enabled:
                trade.state = "exited"
                _add_event(trade, "exit", "target_3_hit", "exited",
                           f"Full exit at target 3: {tgt}", price=tgt)
                return events

    # ── Time Exit ──
    if trade.config.time_exit_enabled and trade.config.max_trade_duration_minutes:
        if trade.entry_time:
            elapsed = (bar.timestamp - trade.entry_time).total_seconds() / 60
            if elapsed >= trade.config.max_trade_duration_minutes:
                trade.state = "exited"
                evt = _add_event(trade, "exit", "active", "exited",
                                 f"Time exit after {elapsed:.0f} minutes",
                                 price=bar.close)
                events.append(evt)
                return events

    # ── Session Close Exit ──
    if trade.config.exit_on_session_close:
        pass  # Requires session engine — placeholder

    trade.last_update = bar.timestamp
    return events


def cancel_trade(trade: ManagedTrade, reason: str = "Manual cancellation") -> list[TradeEvent]:
    """Cancel a pending or active trade."""
    if trade.state in ("exited", "cancelled", "expired"):
        return []
    old = trade.state
    trade.state = "cancelled"
    evt = _add_event(trade, "state_change", old, "cancelled", reason)
    return [evt]


def expire_trade(trade: ManagedTrade) -> list[TradeEvent]:
    """Expire a trade that never entered."""
    if trade.state != "pending_entry":
        return []
    old = trade.state
    trade.state = "expired"
    evt = _add_event(trade, "state_change", old, "expired", "Trade expired")
    return [evt]
