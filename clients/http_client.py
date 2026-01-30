from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Mapping, Optional

import httpx

from infra.rate_limit import RateLimiter
from infra.tokens import TokenProvider


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay_s: float = 0.3
    max_delay_s: float = 5.0

    def backoff(self, attempt: int) -> float:
        # attempt starts at 1
        expo = min(self.max_delay_s, self.base_delay_s * (2 ** (attempt - 1)))
        jitter = random.random() * 0.2 * expo
        return expo + jitter


class HttpTransport:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        token_provider: Optional[TokenProvider] = None,
        rate_limiter: Optional[RateLimiter] = None,
        retry: RetryPolicy = RetryPolicy(),
    ) -> None:
        self.client = client
        self.token_provider = token_provider
        self.rate_limiter = rate_limiter
        self.retry = retry

    async def request(
        self,
        method: str,
        url: str,
        *,
        token: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
        json: Any = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        # Rate limit *before* attempt (and before retry)
        if self.rate_limiter is not None:
            await self._acquire_rl()

        # Token: explicit token wins, otherwise use provider if available
        auth_token = token
        if auth_token is None and self.token_provider is not None:
            auth_token = await self.token_provider.ensure_token()

        req_headers = dict(headers or {})
        if auth_token:
            req_headers.setdefault("Authorization", f"Bearer {auth_token}")

        last_exc: Exception | None = None

        for attempt in range(1, self.retry.max_attempts + 1):
            try:
                resp = await self.client.request(
                    method,
                    url,
                    headers=req_headers,
                    params=params,
                    json=json,
                    timeout=timeout,
                )

                # Retry on common transient statuses
                if resp.status_code in (429, 502, 503, 504):
                    await self._sleep_retry(attempt, resp)
                    continue

                resp.raise_for_status()
                return resp

            except asyncio.CancelledError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as e:
                last_exc = e

                # If it’s a 401 and we have a provider, refresh once
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 401:
                    if self.token_provider is not None:
                        new_token = await self.token_provider.ensure_token()
                        # update header with new token for next attempt
                        req_headers["Authorization"] = f"Bearer {new_token}"
                        await self._sleep_retry(attempt, None)
                        continue

                if attempt >= self.retry.max_attempts:
                    raise

                await self._sleep_retry(attempt, None)

        # should never hit
        assert last_exc is not None
        raise last_exc

    async def _acquire_rl(self) -> None:
        assert self.rate_limiter is not None
        while True:
            allowed, sleep_for = await self.rate_limiter.request_token()
            if allowed:
                return
            if sleep_for is None:
                raise RuntimeError("Rate limiter denied without a sleep suggestion")
            await asyncio.sleep(sleep_for)

    async def _sleep_retry(self, attempt: int, resp: Optional[httpx.Response]) -> None:
        # Prefer Retry-After if present
        if resp is not None:
            ra = resp.headers.get("Retry-After")
            if ra:
                try:
                    await asyncio.sleep(float(ra))
                    return
                except ValueError:
                    pass
        await asyncio.sleep(self.retry.backoff(attempt))
