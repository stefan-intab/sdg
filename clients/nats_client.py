import asyncio
from typing import Optional
from dataclasses import dataclass

from nats.aio.client import Client as NATS
from nats.errors import TimeoutError as NATSTimeoutError, NoServersError
from nats.js.api import StreamConfig, RetentionPolicy, StorageType, Header
from nats.js.errors import NotFoundError

from domain.intabcloud_telemetry_v1_pb2 import Batch
from infra.logging_config import app_logger


@dataclass(frozen=True)
class NATSConfig:
    username: str
    password: str
    server1: str
    port: int

    stream_name: str
    subject: str  # e.g. "telemetry.v1"

    connect_timeout_s: int = 5
    request_timeout_s: float = 5.0
    ping_interval_s: int = 20
    max_outstanding_pings: int = 5
    max_reconnect_attempts: int = -1  # infinite
    reconnect_time_wait_s: int = 1

    # Stream defaults (tune later)
    max_age_s: int = 7 * 24 * 3600
    replicas: int = 1
    

class NATSClient:
    def __init__(self, cfg: NATSConfig) -> None:
        self.cfg = cfg
        self.nc: Optional[NATS] = None
        self.js = None  # JetStream context

    def _server_url(self) -> str:
        # Just a single server for now:
        return f"nats://{self.cfg.username}:{self.cfg.password}@{self.cfg.server1}:{self.cfg.port}"
    
    async def connect(self) -> None:
        if self.nc and self.nc.is_connected:
            return

        self.nc = NATS()

        async def disconnected_cb():
            app_logger.warning("NATS disconnected")

        async def reconnected_cb():
            assert self.nc
            app_logger.warning(f"NATS reconnected to {self.nc.connected_url.netloc}")

        async def error_cb(e):
            app_logger.error(f"NATS error: {e!r}")

        async def closed_cb():
            app_logger.warning("NATS connection closed")

        try:
            await self.nc.connect(
                servers=[self._server_url()],
                connect_timeout=self.cfg.connect_timeout_s,
                ping_interval=self.cfg.ping_interval_s,
                max_outstanding_pings=self.cfg.max_outstanding_pings,
                max_reconnect_attempts=self.cfg.max_reconnect_attempts,
                reconnect_time_wait=self.cfg.reconnect_time_wait_s,
                disconnected_cb=disconnected_cb,
                reconnected_cb=reconnected_cb,
                error_cb=error_cb,
                closed_cb=closed_cb,
            )
        except NoServersError as e:
            raise RuntimeError(f"Could not connect to NATS: {e}") from e

        self.js = self.nc.jetstream()
        await self.ensure_stream()
    
    async def ensure_stream(self) -> None:
        """Idempotently ensure the stream exists and includes our subject."""
        assert self.js is not None

        stream = self.cfg.stream_name
        subject = self.cfg.subject

        try:
            info = await self.js.stream_info(stream)
            # Optional: verify subject is covered; if not, update stream subjects.
            subjects = set(info.config.subjects or [])
            if subject not in subjects:
                new_subjects = sorted(subjects | {subject})
                await self.js.update_stream(
                    StreamConfig(
                        name=stream,
                        subjects=new_subjects,
                        retention=info.config.retention,
                        storage=info.config.storage,
                        max_age=info.config.max_age,
                    )
                )
                app_logger.info(f"Updated stream={stream} to include subject={subject}")
            return

        except NotFoundError:
            # Create it
            cfg = StreamConfig(
                name=stream,
                subjects=[subject],
                retention=RetentionPolicy.LIMITS,
                storage=StorageType.FILE,          # FILE is usually what you want in production
                max_age=self.cfg.max_age_s,
            )
            await self.js.add_stream(cfg)
            app_logger.info(f"Created JetStream stream={stream} subject={subject}")

    async def close(self) -> None:
        if self.nc:
            await self.nc.drain()
            await self.nc.close()
            self.nc = None
            self.js = None
        
    async def publish_batch(self, batch: Batch) -> None:
        """Publish one protobuf Batch with JetStream ack + msg_id dedupe."""
        assert self.js is not None

        payload = batch.SerializeToString()
        subject = self.cfg.subject

        # Use transmission_id for dedupe (JetStream uses Msg-Id header).
        t_id = batch.transmission_id if getattr(batch, "transmission_id", None) else None
        headers = dict()
        if t_id:
            headers["Nats-Msg-Id"] = str(t_id)
            
        try:
            pa = await self.js.publish(
                subject,
                payload,
                timeout=self.cfg.request_timeout_s,
                headers=headers if t_id else None,
            )
            # pa.stream, pa.seq are useful for tracing/metrics
            app_logger.debug(
                f"Published batch stream={pa.stream} seq={pa.seq} "
                f"id={t_id} items={len(batch.logger_batch)}"
            )
        except NATSTimeoutError as e:
            raise RuntimeError("Timed out waiting for JetStream publish ack") from e