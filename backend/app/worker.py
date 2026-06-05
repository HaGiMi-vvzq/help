"""ARQ Worker — background matching, notifications, and maintenance jobs."""

import asyncio
import logging

from arq import Worker
from arq.connections import RedisSettings

from app.core.config import settings

logger = logging.getLogger("arq")


async def run_matching(ctx: dict, need_id: int) -> dict:
    """Background matching job — run full matching pipeline for a need."""
    from app.core.database import async_session
    from app.services.match_engine import run_matching as _run_matching

    async with async_session() as db:
        await _run_matching(db, need_id)
    logger.info("ARQ: matching completed for need_id=%d", need_id)
    return {"need_id": need_id, "status": "done"}


async def cleanup_expired(ctx: dict) -> dict:
    """Periodic cleanup of expired sessions and stale data."""
    logger.info("ARQ: cleanup job started")
    # Placeholder for future cleanup logic
    return {"status": "done"}


async def startup(ctx: dict):
    logger.info("ARQ worker started")


async def shutdown(ctx: dict):
    logger.info("ARQ worker stopped")


class WorkerSettings:
    functions = [run_matching, cleanup_expired]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 20
    poll_delay = 0.5
    keep_result = 3600  # 1 hour


def main():
    worker = Worker(
        functions=WorkerSettings.functions,
        redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
        max_jobs=WorkerSettings.max_jobs,
        poll_delay=WorkerSettings.poll_delay,
        keep_result=WorkerSettings.keep_result,
    )
    worker.run()


if __name__ == "__main__":
    main()
