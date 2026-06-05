"""Rate limiter — in-memory for dev, Redis-backed for production."""

import time
from collections import defaultdict


class RateLimiter:
    """In-memory rate limiter (per-process, for development)."""

    def __init__(self, max_per_minute: int = 10, max_per_hour: int = 100):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        now = time.time()
        bucket = self._buckets[key]

        cutoff = now - 3600
        idx = 0
        while idx < len(bucket) and bucket[idx] < cutoff:
            idx += 1
        if idx > 0:
            bucket = bucket[idx:]
        self._buckets[key] = bucket

        minute_calls = sum(1 for t in bucket if now - t < 60)
        if minute_calls >= self.max_per_minute:
            return False
        if len(bucket) >= self.max_per_hour:
            return False

        bucket.append(now)
        return True

    def check_ip(self, ip: str) -> bool:
        return self.check(f"ip:{ip}")


class RedisRateLimiter:
    """Redis-backed sliding-window rate limiter (shared across workers)."""

    def __init__(self, max_per_minute: int = 10, max_per_hour: int = 100):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour

    async def check(self, key: str) -> bool:
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            now = time.time()
            minute_key = f"rl:min:{key}"
            hour_key = f"rl:hr:{key}"

            async with r.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(minute_key, 0, now - 60)
                pipe.zcard(minute_key)
                pipe.zremrangebyscore(hour_key, 0, now - 3600)
                pipe.zcard(hour_key)
                results = await pipe.execute()

            minute_count = results[1]
            hour_count = results[3]

            if minute_count >= self.max_per_minute:
                return False
            if hour_count >= self.max_per_hour:
                return False

            async with r.pipeline(transaction=True) as pipe:
                pipe.zadd(minute_key, {str(now): now})
                pipe.expire(minute_key, 120)
                pipe.zadd(hour_key, {str(now): now})
                pipe.expire(hour_key, 3700)
                await pipe.execute()

            return True
        except Exception:
            return True  # Fail open — don't block users if Redis is down

    async def check_ip(self, ip: str) -> bool:
        return await self.check(f"ip:{ip}")


# Module-level instances
_rate_limiter: RateLimiter | None = None
_login_limiter: RateLimiter | None = None
_redis_rate_limiter: RedisRateLimiter | None = None
_redis_login_limiter: RedisRateLimiter | None = None


def _use_redis() -> bool:
    try:
        from app.core.redis import is_redis_available
        return is_redis_available()
    except Exception:
        return False


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_login_rate_limiter() -> RateLimiter:
    global _login_limiter
    if _login_limiter is None:
        _login_limiter = RateLimiter(max_per_minute=5, max_per_hour=20)
    return _login_limiter


def get_redis_rate_limiter() -> RedisRateLimiter:
    global _redis_rate_limiter
    if _redis_rate_limiter is None:
        _redis_rate_limiter = RedisRateLimiter()
    return _redis_rate_limiter


def get_redis_login_rate_limiter() -> RedisRateLimiter:
    global _redis_login_limiter
    if _redis_login_limiter is None:
        _redis_login_limiter = RedisRateLimiter(max_per_minute=5, max_per_hour=20)
    return _redis_login_limiter
