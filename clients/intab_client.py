
from httpx import AsyncClient

from infra.tokens import TokenProvider, TokenConfig
from infra.rate_limit import RateLimiter, RateLimiterConfig
from domain.device import Channel

class IntabClient:
    def __init__(
        self,
        base_url: str,
        http_client: AsyncClient,
        rl_cfg: RateLimiterConfig,
        tkn_cfg: TokenConfig,
    ) -> None:
        
        self.base_url = base_url
        self.http_client = http_client
        self.rate_limiter = RateLimiter(cfg=rl_cfg)
        self.token = TokenProvider(
            cfg=tkn_cfg,
            http_client=http_client
        )

        

    async def list_loggers(self) -> list:
        token = await self.token.ensure_token()
        # Use rate limiter
        # httpx.AsyncClient

        return []
    
    
    async def list_logger_channels(self, logger_id: int) -> list:
        token = await self.token.ensure_token()

        return []

    
    async def create_channel(self, logger_id: int, tag: str) -> Channel:
        token = await self.token.ensure_token()
        return Channel(id=1, tag=tag)


    async def get_channel_id_or_none(self, logger_id: int, tag: str) -> int | None:
        """
        Checks if a channels exists by logger_id and tag.
        Returns channel_id when found in REST API, else None
        """
        channels = await self.list_logger_channels(logger_id)

        channel_id = None
        for ch in channels:
            if ch.get("tag") == tag:
                channel_id = ch.get("id")

        return channel_id