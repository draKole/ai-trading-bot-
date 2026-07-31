"""Settings persistence service — read/write non-secret application defaults."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as env_settings
from app.models.application_settings import ApplicationSettings


# Fields that are safe to expose and update through browser APIs
EXPECTED_FIELDS = {
    "trading_mode",
    "data_provider",
    "default_risk_percent",
    "min_risk_reward",
    "max_contracts",
    "max_trades_per_day",
    "max_trades_per_session",
}

# Default values from environment config (used as fallback if no DB row exists)
_DEFAULTS = {
    "trading_mode": env_settings.TRADING_MODE,
    "data_provider": env_settings.DATA_PROVIDER,
    "default_risk_percent": env_settings.DEFAULT_RISK_PERCENT,
    "min_risk_reward": env_settings.DEFAULT_MIN_RISK_REWARD,
    "max_contracts": env_settings.MAX_CONTRACTS,
    "max_trades_per_day": env_settings.MAX_TRADES_PER_DAY,
    "max_trades_per_session": env_settings.MAX_TRADES_PER_SESSION,
}


class SettingsService:
    """Manages persisted application settings.

    Secrets (DB URLs, broker keys, Redis URLs, secret keys) are NEVER
    stored or returned by this service. Only the non-sensitive trading
    defaults exposed by the Settings workspace are managed here.
    """

    @staticmethod
    async def get(db: AsyncSession) -> dict:
        """Return current application settings, merging DB row with env defaults."""
        result = await db.execute(
            select(ApplicationSettings).where(ApplicationSettings.id == 1)
        )
        row = result.scalar_one_or_none()

        if row is None:
            return dict(_DEFAULTS)

        return {
            "trading_mode": row.trading_mode,
            "data_provider": row.data_provider,
            "default_risk_percent": row.default_risk_percent,
            "min_risk_reward": row.min_risk_reward,
            "max_contracts": row.max_contracts,
            "max_trades_per_day": row.max_trades_per_day,
            "max_trades_per_session": row.max_trades_per_session,
        }

    @staticmethod
    async def update(db: AsyncSession, data: dict) -> dict:
        """Validate and persist a partial update of application settings.

        Only known, non-secret fields are accepted. Unknown keys are
        silently dropped — secrets can never be injected through this path.
        """
        result = await db.execute(
            select(ApplicationSettings).where(ApplicationSettings.id == 1)
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = ApplicationSettings(id=1)
            db.add(row)

        updated = False
        for key, value in data.items():
            if key not in EXPECTED_FIELDS:
                continue
            if not hasattr(row, key):
                continue
            setattr(row, key, value)
            updated = True

        if updated:
            await db.flush()

        return await SettingsService.get(db)
