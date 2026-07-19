"""SMT Engine — Smart Money Technique Divergence detection.

Compares correlated instrument pairs at Market Structure swing points
to detect bullish/bearish divergences.

Components:
    - detect_smt_divergence: Swing comparison across instrument pairs
    - SMTService: Persistence and query layer
"""

from app.services.smt.detector import (
    detect_smt_divergence,
    SMTConfig, SMTEvent,
    SMTDirection, SMTMatchingMethod,
)
from app.services.smt.service import SMTService

__all__ = [
    "detect_smt_divergence",
    "SMTConfig", "SMTEvent",
    "SMTDirection", "SMTMatchingMethod",
    "SMTService",
]
