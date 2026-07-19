"""Smoke tests — verify the application boots and core services are reachable."""

import pytest


def test_app_creates():
    """Verify the FastAPI app can be instantiated."""
    from app.main import app
    assert app is not None
    assert app.title == "Drake AI Trading"


def test_config_loads():
    """Verify configuration loads with defaults."""
    from app.core.config import settings
    assert settings.TRADING_MODE == "PAPER"
    assert settings.LIVE_ALLOWED is False
    assert settings.API_PORT == 8000
    assert settings.POSTGRES_DB == "drake_trading"


def test_config_database_url():
    """Verify database URL is constructed correctly."""
    from app.core.config import settings
    url = settings.database_url
    assert "postgresql+asyncpg://" in url
    assert settings.POSTGRES_USER in url


def test_config_redis_url():
    """Verify Redis URL is constructed correctly."""
    from app.core.config import settings
    url = settings.redis_url
    assert "redis://" in url
    assert str(settings.REDIS_PORT) in url


def test_all_service_modules_import():
    """Verify all service modules can be imported."""
    modules = [
        "app.services.market_data",
        "app.services.market_structure",
        "app.services.liquidity",
        "app.services.fvg",
        "app.services.order_blocks",
        "app.services.smt",
        "app.services.sessions",
        "app.services.strategy",
        "app.services.confluence",
        "app.services.risk",
        "app.services.position_sizing",
        "app.services.broker",
        "app.services.order_management",
        "app.services.backtesting",
        "app.services.paper_trading",
        "app.services.trade_journal",
        "app.services.analytics",
        "app.services.dashboard",
        "app.services.ai_analysis",
    ]
    for module_name in modules:
        mod = __import__(module_name, fromlist=["__init__"])
        assert mod is not None, f"Failed to import {module_name}"


def test_broker_adapter_abc():
    """Verify BrokerAdapter ABC defines the required interface."""
    import inspect
    from app.services.broker import BrokerAdapter

    methods = [
        name for name, _ in inspect.getmembers(BrokerAdapter, predicate=inspect.isfunction)
        if not name.startswith('_')
    ]
    required = ["connect", "disconnect", "place_order", "cancel_order", "get_account_summary", "is_connected"]
    for method in required:
        assert method in methods, f"BrokerAdapter missing method: {method}"


def test_signal_dataclass():
    """Verify Signal dataclass can be instantiated."""
    from app.services.strategy import Signal, Direction, SetupType
    from datetime import datetime

    signal = Signal(
        id="test-001",
        strategy_version="0.1.0",
        instrument="MNQ",
        direction=Direction.LONG,
        setup_type=SetupType.FVG_RETRACEMENT,
        entry_price=21000.0,
        stop_loss=20950.0,
        take_profit=21100.0,
        confluence_score=7.5,
        timeframe_context="5m",
        bias="bullish",
        generated_at=datetime.now(),
    )
    assert signal.id == "test-001"
    assert signal.confluence_score == 7.5


def test_risk_profile_defaults():
    """Verify RiskProfile has sensible defaults."""
    from app.services.risk import RiskProfile

    profile = RiskProfile(name="default")
    assert profile.risk_per_trade_pct == 0.01
    assert profile.min_risk_reward == 2.0
    assert profile.max_contracts == 10


def test_live_mode_gate():
    """Verify LIVE_ALLOWED is False by default."""
    from app.core.config import settings
    assert settings.LIVE_ALLOWED is False, "LIVE_ALLOWED must default to False"


def test_confluence_config_threshold():
    """Verify ConfluenceConfig has key attributes."""
    from app.services.confluence import ConfluenceConfig

    config = ConfluenceConfig()
    assert config.min_evidence_sources >= 0
    assert config.fvg_weight > 0
    assert config.smt_weight > 0


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify the health endpoint responds."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "mode" in data
        assert data["mode"] == "PAPER"
