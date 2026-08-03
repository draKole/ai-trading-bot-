"""Market-data health probe edge cases: provider and recent DB-bar contracts."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import pytest
from app.api import monitoring

class Provider:
    def __init__(self, available=True): self.available = available
    async def is_available(self): return self.available

class Result:
    def __init__(self, rows): self.rows = rows
    def all(self): return self.rows
class Session:
    def __init__(self, rows=()): self.rows = rows
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    async def execute(self, query): return Result(self.rows)

@pytest.mark.asyncio
async def test_probe_unavailable_provider(monkeypatch):
    monkeypatch.setattr(monitoring.ProviderRegistry, "list_providers", classmethod(lambda cls: ["test"]))
    monkeypatch.setattr(monitoring.ProviderRegistry, "get", classmethod(lambda cls, name: Provider(False)))
    monkeypatch.setattr("app.core.database.async_session_factory", lambda: Session())
    result = await monitoring._check_market_data_connection()
    assert result["ok"] is False
    assert result["provider_status"] == "unavailable"

@pytest.mark.asyncio
async def test_probe_empty_db(monkeypatch):
    monkeypatch.setattr(monitoring.ProviderRegistry, "list_providers", classmethod(lambda cls: ["test"]))
    monkeypatch.setattr(monitoring.ProviderRegistry, "get", classmethod(lambda cls, name: Provider(True)))
    monkeypatch.setattr("app.core.database.async_session_factory", lambda: Session())
    result = await monitoring._check_market_data_connection()
    assert result["ok"] is False
    assert result["instruments"] == {}

@pytest.mark.asyncio
async def test_probe_partial_instruments(monkeypatch):
    monkeypatch.setattr(monitoring.ProviderRegistry, "list_providers", classmethod(lambda cls: ["test"]))
    monkeypatch.setattr(monitoring.ProviderRegistry, "get", classmethod(lambda cls, name: Provider(True)))
    now = datetime.now(timezone.utc)
    monkeypatch.setattr("app.core.database.async_session_factory", lambda: Session([("ES", 3, now)]))
    result = await monitoring._check_market_data_connection()
    assert result["ok"] is False
    assert result["complete_instruments"] is False
    assert result["last_successful_update"]

@pytest.mark.asyncio
async def test_probe_timeout_is_reported_as_unavailable(monkeypatch):
    class SlowProvider:
        async def is_available(self):
            await asyncio.sleep(3)
            return True
    monkeypatch.setattr(monitoring.ProviderRegistry, "list_providers", classmethod(lambda cls: ["slow"]))
    monkeypatch.setattr(monitoring.ProviderRegistry, "get", classmethod(lambda cls, name: SlowProvider()))
    monkeypatch.setattr("app.core.database.async_session_factory", lambda: Session())
    result = await monitoring._check_market_data_connection()
    assert result["ok"] is False
    assert result["provider_status"] == "unavailable"

@pytest.mark.asyncio
async def test_probe_uses_registered_available_provider_with_fixture_bars(monkeypatch):
    """CI fixture bars still require a genuinely registered provider."""
    monkeypatch.setattr(monitoring.ProviderRegistry, "list_providers", classmethod(lambda cls: ["yfinance"]))
    monkeypatch.setattr(monitoring.ProviderRegistry, "get", classmethod(lambda cls, name: Provider(True)))
    now = datetime.now(timezone.utc)
    rows = [("ES", 1, now), ("MES", 1, now), ("NQ", 1, now), ("MNQ", 1, now)]
    monkeypatch.setattr("app.core.database.async_session_factory", lambda: Session(rows))
    result = await monitoring._check_market_data_connection()
    assert result["ok"] is True
    assert result["provider"] == "yfinance"
    assert result["complete_instruments"] is True

def test_mes_migration_is_head_of_application_settings():
    from pathlib import Path
    migration = Path(__file__).parents[1] / "database/migrations/versions/029_seed_mes_instrument.py"
    source = migration.read_text()
    assert 'down_revision: Union[str, None] = "028_application_settings"' in source
    assert "'MES'" in source
    assert "'Micro E-mini S&P 500'" in source

def test_ci_fixture_entrypoint_sets_backend_import_path():
    from pathlib import Path
    entrypoint = Path(__file__).parents[2] / "docker-entrypoint.sh"
    source = entrypoint.read_text()
    assert "PYTHONPATH=/app/backend" in source
    assert "bootstrap_market_data_fixture.py" in source

def test_runtime_verifier_accepts_direct_full_health_payload():
    """The full-health endpoint exposes components at the document root."""
    from pathlib import Path
    script = (Path(__file__).parents[2] / "scripts/verify_docker_runtime.sh").read_text()
    assert 'health = data.get("health", data)' in script
    assert 'components = health["components"]' in script
    # Ensure strict checks remain attached to the normalized component map.
    assert 'components["market_data"]' in script
    assert 'components["workers"]' in script
    assert 'components["broker"]' in script

def test_autonomous_sync_health_is_safe_before_first_sync():
    from app.services.market_data.autonomous import AutonomousMarketData
    health = AutonomousMarketData().health()
    assert health["last_sync"] is None
    assert health["records"] == 0
    assert health["running"] is False

def test_autonomous_calendar_excludes_weekends():
    from datetime import datetime, timezone
    from app.services.market_data.autonomous import AutonomousMarketData
    days = AutonomousMarketData().trading_days(datetime(2026, 8, 1, tzinfo=timezone.utc), datetime(2026, 8, 3, tzinfo=timezone.utc))
    assert days == ["2026-08-03"]
