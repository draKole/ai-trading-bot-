"""Instrument model — futures contract specifications."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, default="CME")
    tick_size: Mapped[float] = mapped_column(Float, nullable=False)
    tick_value: Mapped[float] = mapped_column(Float, nullable=False)
    multiplier: Mapped[int] = mapped_column(Integer, nullable=False)
    min_contracts: Mapped[int] = mapped_column(Integer, default=1)
    max_contracts: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Instrument {self.symbol}>"


# Default instrument specifications for CME Micro/Mini futures
DEFAULT_INSTRUMENTS = [
    {"symbol": "MNQ", "name": "Micro E-mini Nasdaq-100", "tick_size": 0.25, "tick_value": 0.50,  "multiplier": 2},
    {"symbol": "NQ",  "name": "E-mini Nasdaq-100",       "tick_size": 0.25, "tick_value": 5.00,  "multiplier": 20},
    {"symbol": "MES", "name": "Micro E-mini S&P 500",     "tick_size": 0.25, "tick_value": 1.25,  "multiplier": 5},
    {"symbol": "ES",  "name": "E-mini S&P 500",           "tick_size": 0.25, "tick_value": 12.50, "multiplier": 50},
]
