"""Trade Journal — record every signal, fill, and rejection.

Stores complete trade records including strategy version,
confluence score, triggering conditions, and exit reason.
Essential for post-trade analysis and strategy improvement.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TradeRecord:
    trade_id: str
    strategy_version: str
    instrument: str
    direction: str
    setup_type: str
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    position_size: int = 0
    dollar_risk: float = 0.0
    pnl: float = 0.0
    r_multiple: float = 0.0
    session: str | None = None
    market_bias: str | None = None
    confluence_score: float = 0.0
    triggering_conditions: dict | None = None


@dataclass
class RejectedSignalRecord:
    signal_id: str
    rejection_reason: str
    rejected_at: datetime
    strategy_version: str
    instrument: str
    direction: str
    confluence_score: float


class TradeJournal:
    """Record and query trade history and rejected signals.

    Not yet implemented — interface defined for Phase 5.
    """
    pass
