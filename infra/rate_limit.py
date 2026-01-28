import asyncio
import time


class RateLimiterConfig:
    def __init__(self, rate: int = 100, per: float = 60.0):
        self.rate = rate
        self.per = per
        

class RateLimiter:
    def __init__(self, cfg: RateLimiterConfig):
        self.capacity = cfg.rate
        self.tokens = cfg.rate
        self.refill_rate = cfg.rate / cfg.per # tokens per second
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def request_token(self) -> tuple[bool, float | None]:
        """
        Returns:
        (True, None) if allowed
        (False, retry_after_seconds) if rejected
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill

            # Refill tokens
            refill = elapsed * self.refill_rate
            if refill > 0:
                self.tokens = min(self.capacity, self.tokens + refill)
                self.last_refill = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True, None

            # Not enough tokens: calculate retry-after
            missing = 1 - self.tokens
            retry_after = missing / self.refill_rate
            return False, retry_after
