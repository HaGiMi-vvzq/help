"""Cache service — Redis-backed with graceful fallback."""

import json
import logging

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300  # 5 minutes


async def cache_get(key: str) -> dict | list | None:
    try:
        r = await get_redis()
        val = await r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


async def cache_set(key: str, value: dict | list, ttl: int = DEFAULT_TTL) -> None:
    try:
        r = await get_redis()
        await r.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
    except Exception:
        pass


async def cache_delete(key: str) -> None:
    try:
        r = await get_redis()
        await r.delete(key)
    except Exception:
        pass


async def cache_invalidate_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern."""
    try:
        r = await get_redis()
        keys = await r.keys(pattern)
        if keys:
            await r.delete(*keys)
    except Exception:
        pass
