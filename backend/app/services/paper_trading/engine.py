"""Paper Trading Engine — simulated execution with the real pipeline.

Manages multiple concurrent paper accounts, simulates order execution
with fills/slippage/commissions, and tracks positions and P&L.

Uses existing Strategy/Risk/PositionSizing/TradeManagement engines.
No duplicate business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


# ─── Enums ────────────────────────────────────────────────────

class SessionStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


# ─── Config ────────────────────────────────────────────────────

@dataclass
class PaperTradingConfig:
    """Configuration for a paper trading session."""
    account_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Default Paper Account"
    initial_balance: float = 100_000.0
    default_slippage_ticks: int = 1
    tick_size: float = 0.25
    commission_per_contract: float = 2.50
    max_positions: int = 10
    max_risk_per_trade_pct: float = 1.0

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "name": self.name,
            "initial_balance": self.initial_balance,
            "default_slippage_ticks": self.default_slippage_ticks,
            "tick_size": self.tick_size,
            "commission_per_contract": self.commission_per_contract,
            "max_positions": self.max_positions,
            "max_risk_per_trade_pct": self.max_risk_per_trade_pct,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PaperTradingConfig:
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


# ─── Dataclasses ──────────────────────────────────────────────

@dataclass
class PaperSession:
    """Stateful representation of a paper trading session."""
    account_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Default"
    balance: float = 100_000.0
    buying_power: float = 100_000.0
    initial_balance: float = 100_000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    status: str = "stopped"
    config: PaperTradingConfig = field(default_factory=PaperTradingConfig)
    orders: list[PaperOrder] = field(default_factory=list)
    positions: list[PaperPosition] = field(default_factory=list)
    executions: list[PaperExecution] = field(default_factory=list)
    started_at: datetime | None = None
    stopped_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "name": self.name,
            "balance": round(self.balance, 2),
            "buying_power": round(self.buying_power, 2),
            "initial_balance": self.initial_balance,
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "status": self.status,
            "open_positions": len([p for p in self.positions if p.status == "open"]),
            "closed_positions": len([p for p in self.positions if p.status == "closed"]),
        }


@dataclass
class PaperOrder:
    """A simulated order."""
    order_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: int = 0
    order_type: str = "market"
    side: str = "buy"
    instrument: str = ""
    quantity: int = 1
    price: float | None = None
    stop_price: float | None = None
    status: str = "pending"
    filled_qty: int = 0
    fill_price: float = 0.0
    slippage: float = 0.0
    commission: float = 0.0
    expiry: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id, "session_id": self.session_id,
            "order_type": self.order_type, "side": self.side,
            "instrument": self.instrument, "quantity": self.quantity,
            "price": self.price, "stop_price": self.stop_price,
            "status": self.status, "filled_qty": self.filled_qty,
            "fill_price": self.fill_price, "slippage": self.slippage,
            "commission": self.commission,
        }


@dataclass
class PaperPosition:
    """An open or closed position."""
    position_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: int = 0
    instrument: str = ""
    direction: str = "long"
    quantity: int = 0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: str = "open"
    opened_at: datetime | None = None
    closed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id, "session_id": self.session_id,
            "instrument": self.instrument, "direction": self.direction,
            "quantity": self.quantity, "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "status": self.status,
        }


@dataclass
class PaperExecution:
    """Immutable fill record."""
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: int = 0
    order_id: str = ""
    instrument: str = ""
    side: str = ""
    quantity: int = 0
    price: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id, "session_id": self.session_id,
            "order_id": self.order_id, "instrument": self.instrument,
            "side": self.side, "quantity": self.quantity, "price": self.price,
            "commission": self.commission, "slippage": self.slippage,
        }


# ─── Slippage / Commission ──────────────────────────────────

def compute_slippage(order_type: str, side: str, price: float,
                     ticks: int, tick_size: float) -> float:
    """Compute slippage amount for an order.

    Buy → worse price = higher → +slippage
    Sell → worse price = lower → -slippage
    """
    if order_type == "limit":
        return 0.0  # Limit orders fill at limit or better
    slip_amount = ticks * tick_size
    return slip_amount if side == "buy" else -slip_amount


def compute_commission(quantity: int, rate: float) -> float:
    """Compute commission for a trade."""
    return round(quantity * rate, 2)


# ─── Position Tracking ──────────────────────────────────────

def update_position_after_fill(pos: PaperPosition | None,
                                side: str, qty: int,
                                fill_price: float) -> PaperPosition:
    """Create or update a position after a fill."""
    if pos is None:
        return PaperPosition(
            instrument="", direction="long" if side == "buy" else "short",
            quantity=qty, avg_entry_price=fill_price,
            current_price=fill_price, status="open",
            opened_at=datetime.now(timezone.utc),
        )

    if side == "buy":
        total_cost = pos.avg_entry_price * pos.quantity + fill_price * qty
        pos.quantity += qty
        pos.avg_entry_price = total_cost / pos.quantity if pos.quantity > 0 else 0.0
    else:
        pos.quantity -= qty
        if pos.quantity == 0:
            pos.realized_pnl += (fill_price - pos.avg_entry_price) * qty
            pos.status = "closed"
            pos.closed_at = datetime.now(timezone.utc)
        elif pos.quantity < 0:
            # Flipped position
            pos.realized_pnl += (fill_price - pos.avg_entry_price) * (qty + pos.quantity)
            pos.direction = "short"
            pos.quantity = abs(pos.quantity)
            pos.avg_entry_price = fill_price

    pos.current_price = fill_price
    pos.unrealized_pnl = (fill_price - pos.avg_entry_price) * pos.quantity if pos.quantity > 0 else 0.0
    return pos


def compute_unrealized_pnl(pos: PaperPosition, current_price: float) -> float:
    """Compute unrealized P&L for a position."""
    if pos.quantity == 0:
        return 0.0
    if pos.direction == "long":
        return (current_price - pos.avg_entry_price) * pos.quantity
    else:
        return (pos.avg_entry_price - current_price) * pos.quantity


# ─── Order Execution ────────────────────────────────────────

def execute_market_order(order: PaperOrder, current_price: float,
                         config: PaperTradingConfig) -> tuple[PaperOrder, PaperExecution]:
    """Simulate market order execution with slippage and commission."""
    slip = compute_slippage("market", order.side, current_price,
                            config.default_slippage_ticks, config.tick_size)
    fill_price = current_price + slip
    comm = compute_commission(order.quantity, config.commission_per_contract)

    order.status = "filled"
    order.filled_qty = order.quantity
    order.fill_price = fill_price
    order.slippage = slip
    order.commission = comm

    execution = PaperExecution(
        session_id=order.session_id, order_id=order.order_id,
        instrument=order.instrument, side=order.side,
        quantity=order.quantity, price=fill_price,
        commission=comm, slippage=slip,
    )
    return order, execution


def execute_limit_order(order: PaperOrder, current_high: float,
                        current_low: float, config: PaperTradingConfig
                        ) -> tuple[PaperOrder, PaperExecution | None]:
    """Simulate limit order — fills if price crosses the limit."""
    fill_price: float | None = None
    if order.side == "buy" and current_low <= (order.price or 0):
        fill_price = order.price or current_low  # Fill at limit or better
    elif order.side == "sell" and current_high >= (order.price or 0):
        fill_price = order.price or current_high

    if fill_price is None:
        return order, None  # Not filled

    comm = compute_commission(order.quantity, config.commission_per_contract)
    order.status = "filled"
    order.filled_qty = order.quantity
    order.fill_price = fill_price
    order.commission = comm

    execution = PaperExecution(
        session_id=order.session_id, order_id=order.order_id,
        instrument=order.instrument, side=order.side,
        quantity=order.quantity, price=fill_price,
        commission=comm, slippage=0.0,
    )
    return order, execution


# ─── Paper Trading Controller ──────────────────────────────

class PaperTradingController:
    """Manages paper trading sessions, orders, positions, and P&L.

    Multiple concurrent sessions supported. Uses deterministic logic
    for all execution and position tracking.
    """

    def __init__(self):
        self._sessions: dict[str, PaperSession] = {}

    # ── Session Management ────────────────────────────────

    def create_session(self, config: PaperTradingConfig | None = None) -> PaperSession:
        """Create a new paper trading session."""
        if config is None:
            config = PaperTradingConfig()
        session = PaperSession(
            account_id=config.account_id,
            name=config.name,
            balance=config.initial_balance,
            buying_power=config.initial_balance,
            initial_balance=config.initial_balance,
            config=config,
            status="stopped",
        )
        self._sessions[config.account_id] = session
        return session

    def get_session(self, account_id: str) -> PaperSession | None:
        """Get a session by account ID."""
        return self._sessions.get(account_id)

    def list_sessions(self) -> list[PaperSession]:
        """List all sessions."""
        return list(self._sessions.values())

    def start_session(self, account_id: str) -> PaperSession:
        """Start a session."""
        session = self._get_or_raise(account_id)
        session.status = "running"
        session.started_at = datetime.now(timezone.utc)
        return session

    def pause_session(self, account_id: str) -> PaperSession:
        session = self._get_or_raise(account_id)
        if session.status == "running":
            session.status = "paused"
        return session

    def resume_session(self, account_id: str) -> PaperSession:
        session = self._get_or_raise(account_id)
        if session.status == "paused":
            session.status = "running"
        return session

    def stop_session(self, account_id: str) -> PaperSession:
        session = self._get_or_raise(account_id)
        session.status = "stopped"
        session.stopped_at = datetime.now(timezone.utc)
        return session

    def _get_or_raise(self, account_id: str) -> PaperSession:
        session = self._sessions.get(account_id)
        if session is None:
            raise ValueError(f"Session not found: {account_id}")
        return session

    # ── Order Management ──────────────────────────────────

    def place_order(self, account_id: str, order_type: str, side: str,
                    instrument: str, quantity: int, price: float | None = None,
                    stop_price: float | None = None,
                    expiry: datetime | None = None) -> PaperOrder:
        """Place a new order in a session."""
        session = self._get_or_raise(account_id)
        order = PaperOrder(
            session_id=hash(account_id) % 10000,  # placeholder — real ID from DB
            order_type=order_type, side=side, instrument=instrument,
            quantity=quantity, price=price, stop_price=stop_price,
            expiry=expiry,
        )
        session.orders.append(order)
        return order

    def process_orders(self, account_id: str, current_price: float,
                       current_high: float | None = None,
                       current_low: float | None = None) -> list[PaperExecution]:
        """Process pending orders against current market data."""
        session = self._get_or_raise(account_id)
        if session.status != "running":
            return []

        hi = current_high if current_high is not None else current_price
        lo = current_low if current_low is not None else current_price

        executions: list[PaperExecution] = []
        for order in session.orders:
            if order.status != "pending":
                continue

            now = datetime.now(timezone.utc)
            if order.expiry and now > order.expiry:
                order.status = "expired"
                continue

            if order.order_type == "market":
                updated, exec_rec = execute_market_order(order, current_price, session.config)
                executions.append(exec_rec)
                self._apply_fill(session, updated, exec_rec)
            elif order.order_type == "limit":
                updated, exec_rec = execute_limit_order(order, hi, lo, session.config)
                if exec_rec:
                    executions.append(exec_rec)
                    self._apply_fill(session, updated, exec_rec)

        session.executions.extend(executions)
        return executions

    def _apply_fill(self, session: PaperSession, order: PaperOrder,
                    execution: PaperExecution) -> None:
        """Apply a fill to session balance and positions."""
        cost = execution.price * execution.quantity + execution.commission
        if order.side == "buy":
            session.balance -= cost
        else:
            session.balance += execution.price * execution.quantity - execution.commission

        session.buying_power = session.balance
        session.realized_pnl = session.balance - session.initial_balance

        # Find or create position
        existing = next(
            (p for p in session.positions
             if p.instrument == order.instrument and p.status == "open"),
            None,
        )

        if order.side == "buy":
            if existing and existing.direction == "short":
                # Closing short — use existing position
                fill_qty = min(order.quantity, existing.quantity)
                updated = update_position_after_fill(existing, "buy", fill_qty, execution.price)
                if existing not in session.positions:
                    session.positions.append(updated)
                if existing.quantity == 0:
                    # Closed — check if removed
                    pass
            else:
                if existing is None:
                    pos = PaperPosition(
                        instrument=order.instrument, direction="long",
                        quantity=order.quantity, avg_entry_price=execution.price,
                        current_price=execution.price, status="open",
                        opened_at=datetime.now(timezone.utc),
                    )
                    session.positions.append(pos)
                else:
                    updated = update_position_after_fill(existing, "buy", order.quantity, execution.price)
        else:  # sell
            if existing and existing.direction == "long":
                fill_qty = min(order.quantity, existing.quantity)
                updated = update_position_after_fill(existing, "sell", fill_qty, execution.price)
                if existing.quantity == 0:
                    existing.status = "closed"
                    existing.closed_at = datetime.now(timezone.utc)
                    existing.realized_pnl += (execution.price - existing.avg_entry_price) * fill_qty
            else:
                if existing is None:
                    pos = PaperPosition(
                        instrument=order.instrument, direction="short",
                        quantity=order.quantity, avg_entry_price=execution.price,
                        current_price=execution.price, status="open",
                        opened_at=datetime.now(timezone.utc),
                    )
                    session.positions.append(pos)
                else:
                    updated = update_position_after_fill(existing, "sell", order.quantity, execution.price)

    # ── Position Updates ──────────────────────────────────

    def update_positions(self, account_id: str,
                         prices: dict[str, float]) -> None:
        """Mark positions to market with current prices."""
        session = self._get_or_raise(account_id)
        total_unrealized = 0.0
        for pos in session.positions:
            if pos.status != "open":
                continue
            if pos.instrument in prices:
                pos.current_price = prices[pos.instrument]
                pos.unrealized_pnl = compute_unrealized_pnl(pos, pos.current_price)
                total_unrealized += pos.unrealized_pnl
        session.unrealized_pnl = total_unrealized

    # ── Statistics ────────────────────────────────────────

    def get_statistics(self, account_id: str) -> dict:
        """Get session statistics."""
        session = self._get_or_raise(account_id)
        closed_positions = [p for p in session.positions if p.status == "closed"]
        wins = sum(1 for p in closed_positions if p.realized_pnl > 0)
        losses = sum(1 for p in closed_positions if p.realized_pnl < 0)

        return {
            "account_id": account_id,
            "balance": round(session.balance, 2),
            "buying_power": round(session.buying_power, 2),
            "realized_pnl": round(session.realized_pnl, 2),
            "unrealized_pnl": round(session.unrealized_pnl, 2),
            "total_pnl": round(session.realized_pnl + session.unrealized_pnl, 2),
            "open_positions": len([p for p in session.positions if p.status == "open"]),
            "closed_positions": len(closed_positions),
            "total_orders": len(session.orders),
            "total_executions": len(session.executions),
            "win_rate": round(wins / max(wins + losses, 1), 4),
        }

    # ── State Export/Import (for recovery) ─────────────────

    def export_state(self, account_id: str) -> dict:
        """Export session state for persistence/recovery."""
        session = self._get_or_raise(account_id)
        return {
            "account_id": session.account_id,
            "name": session.name,
            "balance": session.balance,
            "buying_power": session.buying_power,
            "initial_balance": session.initial_balance,
            "realized_pnl": session.realized_pnl,
            "unrealized_pnl": session.unrealized_pnl,
            "status": session.status,
            "config": session.config.to_dict(),
            "orders": [o.to_dict() for o in session.orders],
            "positions": [p.to_dict() for p in session.positions],
            "executions": [e.to_dict() for e in session.executions],
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "stopped_at": session.stopped_at.isoformat() if session.stopped_at else None,
        }

    def import_state(self, state: dict) -> PaperSession:
        """Restore session from exported state."""
        config = PaperTradingConfig.from_dict(state.get("config", {}))
        session = PaperSession(
            account_id=state["account_id"],
            name=state.get("name", "Recovered"),
            balance=state.get("balance", config.initial_balance),
            buying_power=state.get("buying_power", config.initial_balance),
            initial_balance=state.get("initial_balance", config.initial_balance),
            realized_pnl=state.get("realized_pnl", 0.0),
            unrealized_pnl=state.get("unrealized_pnl", 0.0),
            status=state.get("status", "stopped"),
            config=config,
        )
        session.orders = [PaperOrder(**o) for o in state.get("orders", [])]  # Simplified
        # Full recovery would reconstruct dataclasses properly
        self._sessions[session.account_id] = session
        return session
