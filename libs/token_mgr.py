from typing import Optional, Tuple
import asyncio

import httpx
import jwt

from helpers import ts_now



class TokenConfig:
    def __init__(self, username: str, password: str, login_url: str, grace_period: int = 60, default_exp: int = 600):
        self.username = username
        self.password = password
        self.login_url = login_url
        self.grace_period = grace_period
        self.default_exp = default_exp
        # self.use_refresh_token: bool  - implement later
        # self.refresh_url: str  - implement later


class TokenManager:
    def __init__(self, cfg: TokenConfig) -> None:
        self.cfg = cfg
        self._token: Optional[str] = None
        self._expires_at_ts: float = 0.0  # unix timestamp as float
        self._lock = asyncio.Lock()
        self._httpc = httpx.AsyncClient(timeout=10)

    async def ensure_token(self) -> str:
        # Fast path
        now = ts_now()
        if self._token and now < (self._expires_at_ts - 60):  # refresh 60s early
            return self._token

        # Single-flight refresh
        async with self._lock:
            now = ts_now()
            if self._token and now < (self._expires_at_ts - 60):
                return self._token

            token, _expires_at_ts = await self._login()
            self._token = token
            self._expires_at_ts = _expires_at_ts
            return self._token

    async def invalidate(self) -> None:
        async with self._lock:
            self._token = None
            self._expires_at_ts = 0.0

    async def _login(self, retry_after: int = 10) -> Tuple[str, float]:
        while True:  # never back off or quit trying
            try:
                r = await self._httpc.post(
                    self.cfg.login_url,
                    json={"username": self.cfg.username, "password": self.cfg.password}
                )
                r.raise_for_status()

                token = r.json().get("access_token")
                if not token:
                    raise RuntimeError("No access_token in response")
                
                exp_ts = self._extract_exp_time(token)
                if not exp_ts:
                    exp_ts = ts_now() + self.cfg.default_exp

                return token, float(exp_ts)
            
            except Exception as e:
                # log error!
                await asyncio.sleep(retry_after)

    def _extract_exp_time(self, token) -> Optional[int]:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get("exp")
            return int(exp) if exp is not None else None
            
        except Exception as e:
            # log error!
            return None
