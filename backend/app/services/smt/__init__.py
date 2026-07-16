"""SMT Divergence Engine — compare correlated instruments for divergence.

Compares NQ vs ES or MNQ vs MES for bullish/bearish SMT divergence
using objective swing comparisons. Modular — can be enabled/disabled.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SMTDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class SMTEvent:
    instrument_a: str
    instrument_b: str
    timeframe: str
    direction: SMTDirection
    bar_time: datetime
    details: dict


class SMTEngine(ABC):
    """Abstract interface for SMT divergence detection."""

    @abstractmethod
    def detect(
        self, bars_a: list, bars_b: list,
        instrument_a: str, instrument_b: str,
    ) -> list[SMTEvent]:
        """Detect SMT divergence between two correlated instruments."""
        ...
