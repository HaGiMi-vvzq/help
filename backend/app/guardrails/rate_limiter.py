import time
from collections import defaultdict


class RateLimiter:
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


_rate_limiter: RateLimiter | None = None
_login_limiter: RateLimiter | None = None


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
