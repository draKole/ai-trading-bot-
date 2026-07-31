"""Settings API — persisted non-secret application defaults.

Reads from the database, falls back to environment defaults when no row exists.
Secrets (database URLs, broker keys, Redis URLs, secret keys) are NEVER
exposed or accepted by these endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.settings import SettingsService

router = APIRouter()


class SettingsResponse(BaseModel):
    trading_mode: str = "PAPER"
    data_provider: str = "yfinance"
    default_risk_percent: float = 1.0
    min_risk_reward: float = 2.0
    max_contracts: int = 10
    max_trades_per_day: int = 10
    max_trades_per_session: int = 5


class SettingsUpdate(BaseModel):
    """Partial update — only provided fields are changed. Unknown keys ignored."""

    trading_mode: str | None = Field(None, pattern=r"^(PAPER|LIVE)$")
    data_provider: str | None = None
    default_risk_percent: float | None = Field(None, ge=0.0, le=100.0)
    min_risk_reward: float | None = Field(None, gt=0.0)
    max_contracts: int | None = Field(None, ge=1)
    max_trades_per_day: int | None = Field(None, ge=1)
    max_trades_per_session: int | None = Field(None, ge=1)


@router.get("/", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return current non-sensitive application settings."""
    return await SettingsService.get(db)


@router.put("/", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update application settings. Only non-secret fields are accepted.

    Unknown keys are silently dropped — secrets can never be injected
    through this endpoint.
    """
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(400, "No valid settings fields provided")
    return await SettingsService.update(db, data)
