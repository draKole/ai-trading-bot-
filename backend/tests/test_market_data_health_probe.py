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
