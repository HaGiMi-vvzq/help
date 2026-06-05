"""Redis connection management — single shared pool for all workers."""

import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        try:
            await _redis.ping()
            logger.info("Redis connected: %s", settings.REDIS_URL)
        except Exception:
            logger.warning("Redis unavailable at %s — running without cache", settings.REDIS_URL)
            _redis = None  # Reset so we retry on next request
            raise
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
        logger.info("Redis connection closed")


def is_redis_available() -> bool:
    return _redis is not None
