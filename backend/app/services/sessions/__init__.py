"""Session Engine — timezone-aware session classification.

Supports: Asian, London, NY AM, NY PM sessions.
Timezone-aware. Configurable per session: enable/disable, max trades.
"""

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum


class Session(str, Enum):
    ASIAN = "asian"
    LONDON = "london"
    NY_AM = "ny_am"
    NY_PM = "ny_pm"


@dataclass
class SessionConfig:
    session: Session
    enabled: bool = True
    max_trades: int = 5


class SessionEngine:
    """Determine the current trading session from a timestamp."""

    @staticmethod
    def classify(ts: datetime, timezone: str = "US/Eastern") -> Session:
        """Classify a timestamp into a trading session.

        Not yet implemented — placeholder for Phase 2.
        """
        raise NotImplementedError
