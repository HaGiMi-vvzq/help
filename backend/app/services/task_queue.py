"""Task queue service — ARQ-based background jobs via Redis.

Falls back to asyncio.create_task when Redis is unavailable.
"""

import asyncio
import logging
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

_arq_pool = None


async def _ensure_pool():
    global _arq_pool
    if _arq_pool is not None:
        return _arq_pool
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        _arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        logger.info("ARQ pool created at %s", settings.REDIS_URL)
    except Exception:
        logger.warning("ARQ unavailable — falling back to asyncio.create_task")
        _arq_pool = False  # Mark as tried-failed
    return _arq_pool


async def enqueue(task_name: str, *args, **kwargs) -> str | None:
    """Enqueue a background task. Returns job_id or None."""
    pool = await _ensure_pool()
    if pool and pool is not False:
        job = await pool.enqueue_job(task_name, *args, **kwargs)
        return job.job_id
    return None


async def enqueue_or_run(task_name: str, coro: Callable, *args, **kwargs) -> None:
    """Enqueue if Redis is available, otherwise fire-and-forget via asyncio.create_task."""
    job_id = await enqueue(task_name, *args, **kwargs)
    if job_id is None:
        asyncio.create_task(coro(*args, **kwargs))


async def close_queue():
    global _arq_pool
    if _arq_pool and _arq_pool is not False:
        await _arq_pool.close()
        _arq_pool = None
