
from httpx import AsyncClient

from infra.tokens import TokenProvider, TokenConfig
from infra.rate_limit import RateLimiter, RateLimiterConfig
from clients.http_client import HttpTransport
from domain.device import Channel
from infra.logging_config import app_logger


class IntabClient:
    def __init__(
        self,
        base_url: str,
        http_client: AsyncClient,
        rl_cfg: RateLimiterConfig,
        tkn_cfg: TokenConfig,
    ) -> None:
        
        self.base_url = base_url
        self.rate_limiter = RateLimiter(cfg=rl_cfg)
        self.token_provider = TokenProvider(
            cfg=tkn_cfg,
            http_client=http_client
        )
        self.http = HttpTransport(
            client = http_client,
            token_provider=self.token_provider,
            rate_limiter=self.rate_limiter,
        )

    async def list_loggers(self) -> list:
        url = f"{self.base_url}/loggers/internal/active-loggers/"
        params = {
            "manufacturer": "SDG",
            "incl_children": True,
            "limit": 1000,
        }
        app_logger.debug(f"Trying to fetch logger list from: {url}, with params: {params}")
        r = await self.http.request(method="GET",url=url,params=params)

        app_logger.debug(f"Fetched list of loggers: {r.json()}")

        return r.json()
    
    
    async def list_logger_channels(self, logger_id: int) -> list:
        r = await self.http.request(
            method="GET",
            url=f"{self.base_url}/loggers/{logger_id}/channels/"
        )
        app_logger.debug(f"Fetched list of channels: {r.json()}")

        return r.json()

    
    async def create_channel(self, logger_id: int, tag: str) -> Channel:
        payload = self._build_channel_payload(tag)
        r = await self.http.request(
            method="POST",
            url=f"{self.base_url}/loggers/{logger_id}/channels/",
            json=payload,
        )
        body = r.json()
        app_logger.debug(f"Respons from create channel: {r.json()}")

        channel_id = body.get("id")
        api_tag = body.get("tag")
        if channel_id is None or api_tag != tag:
            app_logger.error(f"Error creating channel id {channel_id} with api_tag {api_tag} using tag {tag} and logger_id {logger_id}.")
            raise KeyError()
        
        return Channel(id=channel_id, tag=tag)


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
    

    def _build_channel_payload(self, tag: str) -> dict:
        payload = {
            "tag": tag,
            "name": tag,
            "unit": self._resolve_unit_by_tag(tag),
            "high_from": 0,
            "high_to": 0,
            "low_from": 0,
            "low_to": 0,
            "color": "#000000",
            "decimal_count": 1
            }
        return payload
    
    def _resolve_unit_by_tag(self, tag: str) -> str:
        units = {
            "TEMPERATURE": "°C",
            "HUMIDITY": "%RH",
            "CO2": "CO2",
        }
        return units.get(tag.upper(), tag)

