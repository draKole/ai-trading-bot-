"""Order Block Engine — Order Block detection and lifecycle.

An Order Block represents a significant candle that preceded a strong
directional move confirmed by a BOS/CHoCH event.

Components:
    - detect_order_blocks: Finds OB candles from Market Structure events
    - apply_ob_lifecycle: Tracks creation → touch → mitigation → invalidation
    - OrderBlockService: Persistence and query layer
"""

from app.services.order_block.detector import (
    detect_order_blocks, apply_ob_lifecycle,
    OBConfig, OrderBlock, OBLifecycleEvent,
    OBDirection, OBStatus,
)
from app.services.order_block.service import OrderBlockService

__all__ = [
    "detect_order_blocks", "apply_ob_lifecycle",
    "OBConfig", "OrderBlock", "OBLifecycleEvent",
    "OBDirection", "OBStatus",
    "OrderBlockService",
]
