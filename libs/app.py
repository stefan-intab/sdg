from typing import Optional
import asyncio
import heapq

from sdg import SDGClient
from intab import IntabClient
from token_mgr import TokenConfig
from rate_limiter import RateLimiter, RateLimiterConfig
from libs.loggers import Logger, Channel, LoggerState
from intabcloud_telemetry_v1_pb2 import LoggerBatch, Sample, LoggerStatus
from helpers import ts_now, str_to_ts


class AppConfig:
    out_queue_max = 50_000
    discovery_interval_s: int = 600

class App:
    def __init__(self, app_cfg: AppConfig) -> None:
        self.cfg = app_cfg

        self.sdg = SDGClient(
            base_url="url",
            tkn_cfg=TokenConfig(
                username="username",
                password="password",
                login_url="url"
            ),
            rl_cfg=RateLimiterConfig(),
        )

        self.intab = IntabClient(
            base_url="url",
            tkn_cfg=TokenConfig(
                username="username",
                password="password",
                login_url="url"
            ),
            rl_cfg=RateLimiterConfig()
        )
        self.nats = ""
        
        self.loggers: dict[int, Logger]

        self.heap: list[tuple[int, int, int]] = []  # (next_due_at, lookup_id/serial/IMEI, generation)
        self.heap_lock = asyncio.Lock()

        self.out_queue: asyncio.Queue[LoggerBatch] = asyncio.Queue(maxsize=self.cfg.out_queue_max)

        self.stop_event = asyncio.Event()

    async def startup(self) -> None:
        loggers = await self.intab.list_loggers()
        now = ts_now()

        # initate loggers and store loggers found in intabcloud in self.loggers
        for l in loggers:
            logger = self._initiate_logger(l)
            logger.state._update_due_at()
            self.loggers[logger.id] = logger

        # populate heapqueue with due_at, logger_id, generation
        async with self.heap_lock:
            self.heap.clear()
            for l in self.loggers.values():
                self._push_logger_to_heap(l)
                
    
    async def discovery_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                loggers = await self.intab.list_loggers()
                await self._merge_loggers(loggers)
            except Exception as e:
                # Logg error
                pass
            
            await asyncio.wait_for(self.stop_event.wait(), timeout=self.cfg.discovery_interval_s)
    
    async def scheduler_loop(self) -> None:
        """
        Pops due loggers from heap and submits them to fetch pool via a work queue.
        """
        work_q: asyncio.Queue[int] = asyncio.Queue()
        workers = [
            asyncio.create_task(self)
        ]




    async def fetch_worker_loop(self, work_q: asyncio.Queue[int]) -> None:
        while True:
            logger_id = await work_q.get()
            try:
                logger = self.loggers.get(logger_id)
                if not logger:
                    continue
                if logger.state.in_flight:
                    continue
                logger.state.in_flight = True
                # Fetch logger
            
            finally:
                if logger_id in self.loggers:
                    self.loggers[logger_id].state.in_flight = False
                
                work_q.task_done()

    async def _fetch_one(self, logger: Logger) -> None:
        since = logger.state.last_seen
        try:
            samples, last_seen = await self.sdg.fetch_samples(logger.lookup_id, since=since)

            if samples and last_seen:
                logger.state.last_seen = last_seen
                logger.state.add_successful_tx(last_seen)
                
                channel_tags = logger.get_channel_tags()
                lb = LoggerBatch(
                    logger_id=logger.id,
                    last_seen=last_seen,
                    status=None,
                    samples=None
                )
                
                # Iterate over json and extract values by tag
                for s in samples:
                    dt = s.get("Time")
                    ts = str_to_ts(dt)

                    for tag in channel_tags:
                        channel_id = logger.channel_id_by_tag.get(tag)
                        
                        if not channel_id:
                            # This channel is probably never created. Check intab API and likely create it
                            is_created, channel_id = await self.intab.is_channel_created(logger.id, tag)

                            if is_created is False or not channel_id:
                                channel = await self.intab.create_channel(logger.id, tag)
                                channel_id = channel.id

                        value = s.get(tag)
                        if not value:
                            raise KeyError()
                        
                        sample = Sample(
                            channel_id=channel_id,
                            value=value,
                            ts=ts
                        )
                        
                        lb.samples.append(sample)
                    
                    for tags in status_tags:
                        pass

                # add LoggerBatch to out queue
                await self.out_queue.put(lb)

            else:
                logger.state.inc_error()

            # Update due_at and reschedule in heap
            await self._reschedule(logger)

        except Exception as e:
            pass


    async def _pop_due(self) -> Optional[tuple[int, int]]:
        async with self.heap_lock:
            while self.heap:
                due_at, logger_id, gen = heapq.heappop(self.heap)
                logger = self.loggers.get(logger_id)
                if logger is None:
                    continue
                if gen != logger.state.generation:
                    continue  # stale entry
                return (due_at, logger_id)
            return None
        
    async def _push_back(self, logger_id: int) -> None:
        logger = self.loggers.get(logger_id)
        if not logger:
            return
        async with self.heap_lock:
            self._push_logger_to_heap(logger=logger)

    
    async def _reschedule(self, logger: Logger) -> None:
        logger.state._update_due_at
        logger.state.generation += 1
        
        async with self.heap_lock:
            self._push_logger_to_heap(logger=logger)


    async def _merge_loggers(self, loggers: list[dict]) -> None:
        now = ts_now()
        added = 0
        for l in loggers:
            logger_id: int = l["id"]
            if logger_id in self.loggers:
                continue  

            # Add new loggers to loggers map
            logger = self._initiate_logger(l, now)
            self.loggers[logger.id] = logger
            self._push_logger_to_heap(logger)
            added += 1
        
        if added:
            print(f"Discovery loop added {added} new logger(s)")


    def _push_logger_to_heap(self, logger: Logger) -> None:
        heapq.heappush(
            self.heap, (
                logger.state.due_at,
                logger.id,  # logger_id
                logger.state.generation,
            )
        )

    def _initiate_logger(self, logger: dict, now: int = ts_now()):
        logger_id: int = logger["id"]
        lookup_id: int = logger["lookup_id"]
        logger_tag: str = logger["tag"]
        last_seen: int = logger["last_seen"]

        
        logger_channels = logger.get("channels")
        if not isinstance(logger_channels, list):
            raise KeyError()
        
        channels = []
        for ch in logger_channels:
            channel_id = ch["id"]
            channel_tag = ch["tag"]
            channels.append(Channel(id=channel_id, tag=channel_tag))

        return Logger(
            id=logger_id,
            lookup_id=lookup_id,
            tag = logger_tag,
            channels=channels if channels else [],
            state=LoggerState(due_at=now, last_seen=last_seen)
        )

