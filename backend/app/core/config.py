"""Drake AI Trading — Central Configuration Loader.

All settings are loaded from environment variables or .env file.
Secrets MUST come from environment — never hard-coded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ─── Project Root ────────────────────────────────────────
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent

    # ─── Operating Mode ──────────────────────────────────────
    TRADING_MODE: Literal["BACKTEST", "PAPER", "LIVE"] = "PAPER"
    LIVE_ALLOWED: bool = False  # MUST be explicitly set true for LIVE

    # ─── Database ────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "drake_trading"
    POSTGRES_USER: str = "drake"
    POSTGRES_PASSWORD: str = "drake_dev_password"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ─── Redis ───────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ─── API Server ──────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ─── Authentication ──────────────────────────────────────
    SECRET_KEY: str = "change_me_generate_a_random_64_char_string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ─── Market Data ─────────────────────────────────────────
    DATA_PROVIDER: Literal["yfinance", "polygon", "ibkr", "csv"] = "yfinance"
    POLYGON_API_KEY: str = ""
    IBKR_HOST: str = "127.0.0.1"
    IBKR_PORT: int = 7497
    IBKR_CLIENT_ID: int = 1

    # ─── Risk Defaults ───────────────────────────────────────
    DEFAULT_RISK_PERCENT: float = 0.01
    DEFAULT_MIN_RISK_REWARD: float = 2.0
    MAX_CONTRACTS: int = 10
    MAX_DAILY_LOSS_PERCENT: float = 0.03
    MAX_TRADES_PER_DAY: int = 10
    MAX_TRADES_PER_SESSION: int = 5
    MAX_CONSECUTIVE_LOSSES: int = 3
    STALE_SIGNAL_SECONDS: int = 300

    # ─── Broker ──────────────────────────────────────────────
    BROKER_API_KEY: str = ""
    BROKER_API_SECRET: str = ""
    BROKER_ACCOUNT_ID: str = ""

    # ─── Logging ─────────────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_FILE: str = "/var/log/drake/trading.log"


# Singleton
settings = Settings()
