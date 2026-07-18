"""Market Structure Engine — detect swing points and structure shifts.

Mathematical definitions for:
    - Swing High / Swing Low
    - Higher High / Higher Low / Lower High / Lower Low
    - Break of Structure (BOS)
    - Change of Character (CHoCH)
    - Market Structure Shift (MSS)

All definitions are deterministic and configurable.
"""

from app.services.market_structure.config import MarketStructureConfig, DEFAULT_STRUCTURE_CONFIG
from app.services.market_structure.swing_detector import detect_swings, SwingPoint
from app.services.market_structure.structure_analyzer import (
    analyze_structure,
    StructureEvent,
    StructureEventType,
)
from app.services.market_structure.engine import MarketStructureEngine
from app.services.market_structure.service import MarketStructureService

__all__ = [
    "MarketStructureConfig",
    "DEFAULT_STRUCTURE_CONFIG",
    "detect_swings",
    "SwingPoint",
    "analyze_structure",
    "StructureEvent",
    "StructureEventType",
    "MarketStructureEngine",
    "MarketStructureService",
]
