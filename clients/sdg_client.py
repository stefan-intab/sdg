from httpx import AsyncClient

from infra.tokens import TokenProvider, TokenConfig
from infra.rate_limit import RateLimiterConfig, RateLimiter
from clients.http_client import HttpTransport
from infra.logging_config import app_logger
from utils.time import ts_to_isostr, dt_now_isostr, sdg_time_to_str


class SDGClient:
    def __init__(
        self,
        base_url: str, 
        http_client: AsyncClient,
        tkn_cfg: TokenConfig, 
        rl_cfg: RateLimiterConfig
    ) -> None:
        
        self.base_url = base_url
        self.rate_limiter = RateLimiter(cfg=rl_cfg)
        self.token_provider = TokenProvider(
            cfg=tkn_cfg,
            http_client=http_client
        )
        self.http = HttpTransport(
            client=http_client,
            token_provider=self.token_provider,
            rate_limiter=self.rate_limiter,
        )


    async def fetch_samples(self, lookup_id: int, since: int) -> list:
        """
        Returns a list of samples and the loggers last_seen (the latest sample time)
        """
        from_date = sdg_time_to_str(ts=since)
        now = sdg_time_to_str()
        url = f"{self.base_url}/devices/{lookup_id}/data"

        payload = {
            "from_date": from_date,
            "to_date": now
        }
        app_logger.debug(f"Trying to call url: {url} using payload: {payload}")

        r = await self.http.request("POST", url, json=payload)

        app_logger.debug(f"Fetched samples for device {lookup_id}: {r.json()}")        

        return r.json()
        
