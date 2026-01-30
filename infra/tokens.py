from typing import Optional, Tuple
import asyncio

from httpx import AsyncClient
import jwt

from utils.time import ts_now
from infra.logging_config import app_logger


class TokenConfig:
    def __init__(
            self,
            user_key: str,
            username: str,
            password: str,
            login_url: str,
            grace_period: int = 60,
            default_exp: int = 600
    ) -> None:
        
        self.user_key = user_key
        self.username = username
        self.password = password
        self.login_url = login_url
        self.grace_period = grace_period
        self.default_exp = default_exp
        # self.use_refresh_token: bool  - implement later
        # self.refresh_url: str  - implement later


class TokenProvider:
    def __init__(self, cfg: TokenConfig, http_client: AsyncClient) -> None:
        self.cfg = cfg
        self._token: Optional[str] = None
        self._expires_at_ts: float = 0.0  # unix timestamp as float
        self._lock = asyncio.Lock()
        self._http_client = http_client

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
                app_logger.debug(f"Posting a login request to: {self.cfg.login_url}")
                r = await self._http_client.post(
                    self.cfg.login_url,
                    json={self.cfg.user_key: self.cfg.username, "password": self.cfg.password}
                )
                r.raise_for_status()

                token = r.json().get("access_token")
                if not token:
                    raise RuntimeError("No access_token in response")
                
                exp_ts = self._extract_exp_time(token)
                if not exp_ts:
                    exp_ts = ts_now() + self.cfg.default_exp
                
                app_logger.debug(f"Logged in and recieved token: {token}, and extracted expiration time: {exp_ts}")

                return token, float(exp_ts)
            
            except Exception as e:
                app_logger.error(f"Error at login attempt to: {self.cfg.login_url}, error: {e}")
                await asyncio.sleep(retry_after)

    def _extract_exp_time(self, token) -> Optional[int]:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get("exp")
            return int(exp) if exp is not None else None
            
        except Exception as e:
            # log error!
            return None
