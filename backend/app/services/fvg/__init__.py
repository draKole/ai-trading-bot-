"""FVG Engine — Fair Value Gap detection and lifecycle management.

Components:
    - FVG Detector: 3-candle imbalance pattern detection
    - Lifecycle Manager: creation → first touch → partial fill → mitigated → invalidated
    - FVGService: persistence and query layer
"""

from app.services.fvg.detector import (
    detect_fvgs, apply_lifecycle,
    FVGConfig, FVG, FVGLifecycleEvent,
    FVGDirection, FVGStatus,
)
from app.services.fvg.service import FVGService

__all__ = [
    "detect_fvgs", "apply_lifecycle",
    "FVGConfig", "FVG", "FVGLifecycleEvent",
    "FVGDirection", "FVGStatus",
    "FVGService",
]
