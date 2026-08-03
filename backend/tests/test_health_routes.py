"""Route registration contracts for liveness and comprehensive health checks."""
from app.main import app

def test_health_full_is_available_at_versioned_and_compatibility_paths():
    paths = {route.path for route in app.routes}
    assert "/api/v1/health/full" in paths
    assert "/health/full" in paths

def test_fixture_entrypoint_uses_backend_pythonpath():
    from pathlib import Path
    source = (Path(__file__).parents[2] / "docker-entrypoint.sh").read_text()
    assert "PYTHONPATH=/app/backend${PYTHONPATH:+:$PYTHONPATH} python scripts/bootstrap_market_data_fixture.py" in source
