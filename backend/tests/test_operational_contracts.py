"""Release-critical API and Docker configuration contracts.

These fast checks cover the operational guarantees that can regress without
requiring a running Docker daemon or external PostgreSQL/Redis services.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import subprocess

import yaml
from fastapi.routing import APIRoute


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_api_does_not_register_duplicate_method_path_pairs() -> None:
    """Duplicate method/path pairs create ambiguous routing and OpenAPI warnings."""
    from app.main import app

    method_paths = [
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    ]
    duplicates = [
        item for item, count in Counter(method_paths).items() if count > 1
    ]

    assert not duplicates, f"Duplicate API route registrations: {duplicates}"


def test_openapi_operation_ids_are_unique() -> None:
    """Every OpenAPI operation must be uniquely addressable by generated clients."""
    from app.main import app

    operations = [
        operation
        for path_item in app.openapi()["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    operation_ids = [operation["operationId"] for operation in operations]
    duplicates = [
        item for item, count in Counter(operation_ids).items() if count > 1
    ]

    assert not duplicates, f"Duplicate OpenAPI operation IDs: {duplicates}"


def test_docker_entrypoint_has_valid_bash_syntax() -> None:
    """A syntax error here would prevent migrations and API startup entirely."""
    entrypoint = REPOSITORY_ROOT / "docker-entrypoint.sh"

    assert entrypoint.is_file()
    result = subprocess.run(
        ["bash", "-n", str(entrypoint)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_compose_operational_safety_contract() -> None:
    """Compose must retain PAPER-safe startup and dependency health gates."""
    compose_path = REPOSITORY_ROOT / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    api = compose["services"]["api"]
    environment = dict(item.split("=", 1) for item in api["environment"])

    assert environment["TRADING_MODE"] == "PAPER"
    assert environment["LIVE_ALLOWED"].lower() == "false"
    assert api["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert api["depends_on"]["redis"]["condition"] == "service_healthy"

    assert compose["services"]["postgres"]["healthcheck"]
    assert compose["services"]["redis"]["healthcheck"]
