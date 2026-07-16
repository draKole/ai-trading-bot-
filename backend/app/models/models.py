"""SQLAlchemy ORM Models — Phase 0 placeholder.

Full schema will be created in Phase 1 (Market Data & Normalized Data Model).
This module provides the Base import for Alembic migration detection.
"""

from app.core.database import Base

# Models will be imported here as they are created:
# from app.models.instrument import Instrument
# from app.models.bar import Bar
# from app.models.signal import Signal
# from app.models.trade import Trade
# etc.

__all__ = ["Base"]
