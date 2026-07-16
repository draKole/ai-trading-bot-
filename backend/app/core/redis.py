"""Redis client for caching, pub-sub, and real-time state (kill switch)."""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings

redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Returns a connected Redis client. Creates one if needed."""
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return redis_client


async def check_redis_connection() -> bool:
    """Verify Redis connectivity. Returns True if healthy."""
    try:
        r = await get_redis()
        await r.ping()
        return True
    except Exception:
        return False


async def close_redis() -> None:
    """Close the Redis connection gracefully."""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
