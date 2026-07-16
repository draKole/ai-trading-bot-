"""Pytest fixtures for Drake AI Trading tests."""

import pytest
from pathlib import Path
import sys

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def test_settings():
    """Override settings for testing."""
    from app.core.config import Settings
    return Settings(
        TRADING_MODE="PAPER",
        LIVE_ALLOWED=False,
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_DB="drake_test",
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        SECRET_KEY="test_secret_key_not_for_production",
    )
