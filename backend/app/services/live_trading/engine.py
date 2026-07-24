"""Live Trading Engine — real broker execution with safety controls.

Orchestrates live trading sessions, routes signals through the broker
adapter, enforces safety limits, tracks positions and P&L.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.services.broker.base import (
    BrokerAdapter, BrokerOrder, BrokerPosition, BrokerAccount, BrokerEvent,
    ConnectionState,
)


# ─── Config ────────────────────────────────────────────────────

@dataclass
class LiveTradingConfig:
    """Configuration for a live trading session."""
    account_id: str = field(default_factory=lambda: str(uuid4()))
    broker: str = "tradovate"
    initial_balance: float = 100_000.0
    max_daily_loss: float = 1_000.0
    max_open_positions: int = 5
    max_account_risk_pct: float = 3.0
    heartbeat_timeout_seconds: int = 60
    auto_reconnect: bool = True
    halt_on_connection_loss: bool = True
    duplicate_order_prevention: bool = True

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id, "broker": self.broker,
            "initial_balance": self.initial_balance,
            "max_daily_loss": self.max_daily_loss,
            "max_open_positions": self.max_open_positions,
            "max_account_risk_pct": self.max_account_risk_pct,
            "heartbeat_timeout_seconds": self.heartbeat_timeout_seconds,
            "auto_reconnect": self.auto_reconnect,
            "halt_on_connection_loss": self.halt_on_connection_loss,
            "duplicate_order_prevention": self.duplicate_order_prevention,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LiveTradingConfig:
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


# ─── Session ───────────────────────────────────────────────────

@dataclass
class LiveTradingSession:
    """Stateful live trading session."""
    account_id: str = field(default_factory=lambda: str(uuid4()))
    broker_name: str = "tradovate"
    connection_state: str = "disconnected"
    balance: float = 100_000.0
    buying_power: float = 100_000.0
    initial_balance: float = 100_000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    daily_pnl: float = 0.0
    daily_loss: float = 0.0
    killed: bool = False
    config: LiveTradingConfig = field(default_factory=LiveTradingConfig)
    adapter: BrokerAdapter | None = None
    pending_orders: list[BrokerOrder] = field(default_factory=list)
    open_positions: list[BrokerPosition] = field(default_factory=list)
    executions: list[dict] = field(default_factory=list)
    event_log: list[BrokerEvent] = field(default_factory=list)
    started_at: datetime | None = None
    stopped_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id, "broker": self.broker_name,
            "connection_state": self.connection_state,
            "balance": round(self.balance, 2),
            "buying_power": round(self.buying_power, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "open_positions": len(self.open_positions),
            "pending_orders": len(self.pending_orders),
            "killed": self.killed,
        }


# ─── Safety Controller ────────────────────────────────────────

class SafetyController:
    """Enforces safety limits on live trading."""

    def __init__(self, config: LiveTradingConfig):
        self.config = config
        self._order_ids: set[str] = set()
        self._daily_loss: float = 0.0

    def check_order(self, order: BrokerOrder, session: LiveTradingSession) -> tuple[bool, str]:
        """Validate an order before sending to broker. Returns (allowed, reason)."""
        if session.killed:
            return False, "Emergency kill switch active"

        if session.connection_state != "connected":
            return False, "Not connected to broker"

        open_count = len(session.open_positions)
        if open_count >= self.config.max_open_positions:
            return False, f"Max open positions reached: {open_count}/{self.config.max_open_positions}"

        if self.config.duplicate_order_prevention and order.order_id in self._order_ids:
            return False, "Duplicate order detected"

        if self._daily_loss + abs(session.daily_loss) > self.config.max_daily_loss:
            return False, f"Daily loss limit exceeded: {self.config.max_daily_loss}"

        self._order_ids.add(order.order_id)
        return True, "OK"

    def record_loss(self, loss: float) -> None:
        self._daily_loss += abs(loss)

    def emergency_stop(self, session: LiveTradingSession) -> None:
        """Emergency kill switch — halt all trading."""
        session.killed = True
        session.event_log.append(BrokerEvent(
            event_type="kill_switch",
            detail="EMERGENCY STOP activated — all trading halted",
        ))

    def check_connection(self, session: LiveTradingSession) -> bool:
        """Check if connection is healthy. Returns True if OK."""
        if session.connection_state != "connected":
            if self.config.halt_on_connection_loss:
                self.emergency_stop(session)
            return False
        return True


# ─── Live Trading Controller ──────────────────────────────────

class LiveTradingController:
    """Orchestrates live trading sessions with safety controls.

    Routes signals through BrokerAdapter, validates with SafetyController,
    tracks fills and positions. Never duplicates pipeline logic.
    """

    def __init__(self):
        self._sessions: dict[str, LiveTradingSession] = {}

    def create_session(self, config: LiveTradingConfig,
                       adapter: BrokerAdapter | None = None) -> LiveTradingSession:
        session = LiveTradingSession(
            account_id=config.account_id,
            broker_name=config.broker,
            initial_balance=config.initial_balance,
            balance=config.initial_balance,
            buying_power=config.initial_balance,
            config=config,
            adapter=adapter,
        )
        session.safety = SafetyController(config)
        self._sessions[config.account_id] = session
        return session

    def get_session(self, account_id: str) -> LiveTradingSession | None:
        return self._sessions.get(account_id)

    def list_sessions(self) -> list[LiveTradingSession]:
        return list(self._sessions.values())

    async def connect(self, account_id: str) -> bool:
        session = self._get_or_raise(account_id)
        if session.adapter is None:
            return False
        ok = await session.adapter.connect()
        if ok:
            session.connection_state = "connected"
            session.started_at = datetime.now(timezone.utc)
            acct = await session.adapter.get_account()
            session.balance = acct.balance
            session.buying_power = acct.buying_power
        return ok

    async def disconnect(self, account_id: str) -> bool:
        session = self._get_or_raise(account_id)
        if session.adapter is None:
            return True
        ok = await session.adapter.disconnect()
        session.connection_state = "disconnected"
        session.stopped_at = datetime.now(timezone.utc)
        return ok

    async def place_order(self, account_id: str, order: BrokerOrder) -> dict:
        """Place an order with safety checks."""
        session = self._get_or_raise(account_id)
        if session.adapter is None:
            return {"status": "rejected", "reason": "No broker adapter"}

        allowed, reason = session.safety.check_order(order, session)
        if not allowed:
            return {"status": "rejected", "reason": reason}

        result = await session.adapter.place_order(order)
        session.pending_orders.append(result)

        # Track executions
        if result.status == "filled":
            session.executions.append({
                "order_id": result.order_id,
                "broker_order_id": result.broker_order_id,
                "instrument": result.instrument,
                "action": result.action,
                "quantity": result.filled_qty,
                "price": result.avg_fill_price,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return {"status": result.status, "order": result.to_dict()}

    async def cancel_order(self, account_id: str, order_id: str) -> dict:
        session = self._get_or_raise(account_id)
        if session.adapter is None:
            return {"status": "error", "reason": "No broker adapter"}
        ok = await session.adapter.cancel_order(order_id)
        return {"status": "cancelled" if ok else "error"}

    async def sync_positions(self, account_id: str):
        """Sync positions from broker."""
        session = self._get_or_raise(account_id)
        if session.adapter is None:
            return
        positions = await session.adapter.get_positions()
        session.open_positions = positions
        unrealized = sum(p.unrealized_pnl for p in positions)
        session.unrealized_pnl = unrealized

    async def sync_account(self, account_id: str):
        """Sync account info from broker."""
        session = self._get_or_raise(account_id)
        if session.adapter is None:
            return
        acct = await session.adapter.get_account()
        session.balance = acct.balance
        session.buying_power = acct.buying_power
        session.realized_pnl = acct.realized_pnl

    def emergency_stop(self, account_id: str) -> dict:
        """Emergency kill switch."""
        session = self._get_or_raise(account_id)
        session.safety.emergency_stop(session)
        return {
            "account_id": account_id,
            "status": "killed",
            "message": "Emergency stop activated — all trading halted",
        }

    def get_statistics(self, account_id: str) -> dict:
        session = self._get_or_raise(account_id)
        return {
            "account_id": account_id,
            "broker": session.broker_name,
            "connection_state": session.connection_state,
            "balance": round(session.balance, 2),
            "buying_power": round(session.buying_power, 2),
            "realized_pnl": round(session.realized_pnl, 2),
            "unrealized_pnl": round(session.unrealized_pnl, 2),
            "daily_pnl": round(session.daily_pnl, 2),
            "open_positions": len(session.open_positions),
            "pending_orders": len(session.pending_orders),
            "total_executions": len(session.executions),
            "killed": session.killed,
        }

    def _get_or_raise(self, account_id: str) -> LiveTradingSession:
        session = self._sessions.get(account_id)
        if session is None:
            raise ValueError(f"Session not found: {account_id}")
        return session
