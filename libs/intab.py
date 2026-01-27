
# import rate_limiter
from token_mgr import TokenManager, TokenConfig
from rate_limiter import RateLimiter, RateLimiterConfig
from loggers import Channel

class IntabClient:
    def __init__(self, tkn_cfg: TokenConfig, rl_cfg: RateLimiterConfig, base_url: str) -> None:
        self.token_mgr = TokenManager(cfg=tkn_cfg)
        self.rate_limiter = RateLimiter(cfg=rl_cfg)
        self.base_url = base_url
        # Use a httpx per Client or per App?

    async def list_loggers(self) -> list:
        token = await self.token_mgr.ensure_token()
        # Use rate limiter
        # httpx.AsyncClient

        return []
    
    
    async def list_logger_channels(self, logger_id: int) -> list:
        token = await self.token_mgr.ensure_token()

        return []

    
    async def create_channel(self, logger_id: int, tag: str) -> Channel:
        token = await self.token_mgr.ensure_token()
        return Channel(id=1, tag=tag)


    async def is_channel_created(self, logger_id: int, tag: str) -> tuple[bool, int | None]:
        channels = await self.list_logger_channels(logger_id)

        is_created = False
        channel_id = None

        for ch in channels:
            if ch.get(tag):
                is_created = True
                channel_id = ch.get("id")

        return is_created, channel_id