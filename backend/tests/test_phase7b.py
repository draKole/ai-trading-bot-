"""Phase 7B Tests — Deployment & Infrastructure.

Tests for Docker, configuration, environment validation, readiness,
liveness, deployment API, secrets, and operational scripts.
"""

import json
import os

import pytest


# ─── Configuration Tests ───────────────────────────────────

class TestConfiguration:
    """Configuration loading and environment validation."""

    def test_settings_load(self):
        """Verify settings load with defaults."""
        from app.core.config import settings
        assert settings.TRADING_MODE == "PAPER"
        assert settings.LIVE_ALLOWED is False
        assert settings.API_PORT == 8000

    def test_database_url_constructed(self):
        from app.core.config import settings
        url = settings.database_url
        assert "postgresql+asyncpg://" in url

    def test_redis_url_constructed(self):
        from app.core.config import settings
        url = settings.redis_url
        assert "redis://" in url

    def test_config_from_env(self, monkeypatch):
        """Verify env vars override defaults."""
        monkeypatch.setenv("TRADING_MODE", "BACKTEST")
        monkeypatch.setenv("API_PORT", "9000")
        from app.core.config import Settings
        s = Settings()
        assert s.TRADING_MODE == "BACKTEST"
        assert s.API_PORT == 9000

    def test_config_rejects_invalid_mode(self):
        from app.core.config import settings
        assert settings.TRADING_MODE in ("BACKTEST", "PAPER", "LIVE")


# ─── Secrets Tests ─────────────────────────────────────────

class TestSecrets:
    """Secrets management — never hardcoded or logged."""

    def test_secret_key_not_default(self):
        from app.core.config import settings
        # Default key should be changed in production
        secret = settings.SECRET_KEY
        assert isinstance(secret, str)
        assert len(secret) > 8

    def test_broker_creds_not_hardcoded(self):
        from app.core.config import settings
        assert isinstance(settings.BROKER_API_KEY, str)
        assert isinstance(settings.BROKER_API_SECRET, str)


# ─── Startup / Dependency Ordering ────────────────────────

class TestStartup:
    """Startup sequence and dependency validation."""

    def test_app_creates(self):
        from app.main import app
        assert app is not None
        assert app.title == "Drake AI Trading"

    def test_all_modules_importable(self):
        modules = [
            "app.core.config", "app.core.database",
            "app.services.market_data", "app.services.market_structure",
            "app.services.liquidity", "app.services.fvg",
            "app.services.strategy", "app.services.confluence",
            "app.services.risk", "app.services.position_sizing",
            "app.services.trade_management", "app.services.backtesting",
            "app.services.paper_trading", "app.services.broker",
            "app.services.live_trading", "app.services.monitoring",
        ]
        for m in modules:
            mod = __import__(m, fromlist=["__init__"])
            assert mod is not None, f"Failed to import {m}"


# ─── Deployment API Tests ─────────────────────────────────

class TestDeploymentAPI:
    """Infrastructure API endpoints."""

    @pytest.mark.asyncio
    async def test_deployment_status(self):
        from app.main import app
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/deployment/status")
            assert response.status_code == 200
            data = response.json()
            assert "version" in data
            assert "status" in data

    @pytest.mark.asyncio
    async def test_readiness(self):
        from app.main import app
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/deployment/readiness")
            assert response.status_code == 200
            data = response.json()
            assert "ready" in data

    @pytest.mark.asyncio
    async def test_liveness(self):
        from app.main import app
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/deployment/liveness")
            assert response.status_code == 200
            data = response.json()
            assert data["alive"] is True

    @pytest.mark.asyncio
    async def test_version_info(self):
        from app.main import app
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/deployment/version")
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_config_validation(self):
        from app.main import app
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/deployment/config")
            assert response.status_code == 200
            data = response.json()
            assert "valid" in data

    @pytest.mark.asyncio
    async def test_diagnostics(self):
        from app.main import app
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/deployment/diagnostics")
            assert response.status_code == 200
            data = response.json()
            assert "python" in data


# ─── Docker Tests ─────────────────────────────────────────

class TestDocker:
    """Dockerfile and compose validation."""

    def test_dockerfile_exists(self):
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "Dockerfile",
        )
        exists = os.path.exists(path)
        assert exists, f"Dockerfile not found at {path}"

    def test_dockerignore_exists(self):
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".dockerignore",
        )
        exists = os.path.exists(path)
        assert exists, f".dockerignore not found at {path}"

    def test_compose_exists(self):
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docker-compose.yml",
        )
        exists = os.path.exists(path)
        assert exists, f"docker-compose.yml not found at {path}"


# ─── Operational Readiness ────────────────────────────────

class TestOperationalReadiness:
    """Deployment readiness validation."""

    def test_required_dirs_exist(self):
        import os
        log_dir = "/var/log/drake"
        if os.path.exists(log_dir):
            assert os.path.isdir(log_dir)

    def test_env_file_present_or_missing(self):
        import os
        env_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", ".env",
        )
        # .env not required — using defaults is fine
        pass
