"""Application settings ORM model — persisted non-secret trading defaults."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApplicationSettings(Base):
    """Singleton row of safe, non-sensitive application/trading defaults.

    Secrets (broker keys, database URLs, Redis URLs, secret keys) are NEVER
    stored here — those remain in environment variables only. This table
    holds user-facing defaults that the Settings workspace can safely
    display and update through the browser API.
    """

    __tablename__ = "application_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    trading_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PAPER",
    )  # PAPER or LIVE
    data_provider: Mapped[str] = mapped_column(
        String(30), nullable=False, default="yfinance",
    )
    default_risk_percent: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
    )
    min_risk_reward: Mapped[float] = mapped_column(
        Float, nullable=False, default=2.0,
    )
    max_contracts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10,
    )
    max_trades_per_day: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10,
    )
    max_trades_per_session: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow,
    )
