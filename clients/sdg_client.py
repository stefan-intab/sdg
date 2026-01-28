import asyncio
from httpx import AsyncClient

from infra.tokens import TokenProvider, TokenConfig
from infra.rate_limit import RateLimiterConfig, RateLimiter


class SDGClient:
    def __init__(
        self,
        base_url: str, 
        http_client: AsyncClient,
        tkn_cfg: TokenConfig, 
        rl_cfg: RateLimiterConfig
    ) -> None:
        
        self.base_url = base_url
        self.http_client = http_client
        self.rate_limiter = RateLimiter(cfg=rl_cfg)
        self.token = TokenProvider(
            cfg=tkn_cfg,
            http_client=http_client
        )
        

    async def fetch_samples(self, lookup_id: int, since: int) -> tuple[list, int | None]:
        """
        Returns a list of samples and the loggers last_seen (the latest sample time)
        """
        is_allowed = False
        while not is_allowed:
            is_allowed, sleep_for = await self.rate_limiter.request_token()

            if not is_allowed:
                if sleep_for:
                    await asyncio.sleep(sleep_for)
                else:
                    raise RuntimeError()

        token = await self.token.ensure_token()

        # httpx.AsyncClient
        # Make actual http request

        # convert sample times to int
        # find lastest sample time

        return [], 1212
        
