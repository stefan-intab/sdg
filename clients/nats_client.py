import asyncio
from typing import List, Dict, Any

from domain.intabcloud_telemetry_v1_pb2 import LoggerBatch

class NATSConfig:
    username: str
    password: str
    server1: str
    port: int
    
    def __init__(self, username: str, password: str, server1: str, port: int):
        self.username = username
        self.password = password
        self.server1 = server1
        self.port = port

class NATSClient:
    def __init__(self, cfg: NATSConfig) -> None:
        self.cfg = cfg
        
    async def publish_batch(self, samples: List[LoggerBatch]) -> None:
        # TODO: implement real NATS JetStream publish
        await asyncio.sleep(0.02)