"""Infrastructure API — deployment status, version, readiness, liveness."""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()

BUILD_INFO = {
    "version": "1.0.0",
    "build_time": datetime.now(timezone.utc).isoformat(),
    "python_version": "3.12",
    "environment": "development",
}


@router.get("/deployment/status")
async def deployment_status():
    """Get deployment status and version info."""
    return {
        **BUILD_INFO,
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/deployment/version")
async def version_info():
    """Get version and build information."""
    return BUILD_INFO


@router.get("/deployment/readiness")
async def readiness():
    """Readiness check — probes critical dependencies (database, redis).

    Returns 200 with ready=true only when all critical dependencies are
    healthy. Container orchestrators can use this for rolling deployments
    and to delay traffic until the instance is fully operational.
    """
    from app.core.database import check_db_connection
    from app.core.redis import check_redis_connection

    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()

    checks = {
        "api": True,
        "database": db_ok,
        "redis": redis_ok,
        "migrations_applied": True,  # verified at startup by entrypoint
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/deployment/liveness")
async def liveness():
    """Liveness check — is the process alive."""
    return {
        "alive": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/deployment/config")
async def config_validation():
    """Validate required configuration."""
    from app.core.config import settings

    checks = {
        "database_url": bool(settings.database_url),
        "redis_url": bool(settings.redis_url),
        "secret_key_set": settings.SECRET_KEY != "change_me_generate_a_random_64_char_string",
        "trading_mode": settings.TRADING_MODE,
        "live_allowed": settings.LIVE_ALLOWED,
    }
    return {
        "valid": all(v for k, v in checks.items() if k != "live_allowed"),
        "checks": checks,
    }


@router.get("/deployment/diagnostics")
async def diagnostics():
    """Full environment diagnostics."""
    import platform
    import sys

    return {
        "python": {
            "version": sys.version,
            "platform": platform.platform(),
            "implementation": platform.python_implementation(),
        },
        "build": BUILD_INFO,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
