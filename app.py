from typing import Optional
import asyncio
import heapq
import statistics
from httpx import AsyncClient

from clients.sdg_client import SDGClient
from clients.intab_client import IntabClient
from clients.nats_client import NATSClient, NATSConfig
from infra.tokens import TokenConfig
from infra.rate_limit import RateLimiter, RateLimiterConfig
from domain.device import Device, Channel, ScheduleState
from domain.intabcloud_telemetry_v1_pb2 import LoggerBatch, Sample, LoggerSignal, SignalType
from utils.time import ts_now, str_to_ts
from infra.logging_config import app_logger
import config


class AppConfig:
    out_queue_max = 50_000
    discovery_interval_s = 600
    worker_count = 10
    scheduler_tick_s = 1  # fallback sleep when heap is empty

class Brigde:
    def __init__(self, app_cfg: AppConfig) -> None:
        self.cfg = app_cfg
        self.http_client = AsyncClient(
            timeout=10
        )

        # Set up SDG client
        self.sdg = SDGClient(
            base_url="url",
            http_client=self.http_client,
            tkn_cfg=TokenConfig(
                username=config.SDG_API_USERNAME,
                password=config.SDG_API_PASSWORD,
                login_url=config.SDG_API_BASE_URL,
            ),
            rl_cfg=RateLimiterConfig(),
        )
        # Set up intab client
        self.intab = IntabClient(
            base_url="url",
            http_client=self.http_client,
            tkn_cfg=TokenConfig(
                username=config.INTAB_API_USERNAME,
                password=config.INTAB_API_PASSWORD,
                login_url=config.INTAB_API_BASE_URL,
            ),
            rl_cfg=RateLimiterConfig()
        )
        
        # Set up NATS
        self.nats = NATSClient(
            NATSConfig(
                username=config.NATS_USERNAME,
                password=config.NATS_PASSWORD,
                server1=config.NATS_SERVER1,
                port=int(config.NATS_PORT),
            )
        )
        
        self.devices: dict[int, Device] = {}
        self.unique_device_ids: set[int] = set()

        self.heap: list[tuple[int, int, int]] = []  # (next_due_at, lookup_id/serial/IMEI, generation)
        self.heap_lock = asyncio.Lock()

        self.publish_queue: asyncio.Queue[LoggerBatch] = asyncio.Queue(maxsize=self.cfg.out_queue_max)

        self.stop_event = asyncio.Event()

    async def startup(self) -> None:
        loggers = await self.intab.list_loggers()
    
        # initate loggers and store loggers found in intabcloud in self.loggers
        for l in loggers:
            device = self._initiate_logger(l)
            device.schedule._update_due_at()
            self.devices[device.id] = device
            self.unique_device_ids.add(device.id)

        # populate heapqueue with due_at, logger_id, generation
        async with self.heap_lock:
            self.heap.clear()
            for d in self.devices.values():
                self._push_logger_to_heap(d)
                
        app_logger.debug(f"Startup has completed. Initiated devices: {self.devices}")
                
    
    async def discovery_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                loggers = await self.intab.list_loggers()
                await self._merge_loggers(loggers)
            except Exception as e:
                app_logger.error(f"Error in discovery loop: {e}")
            
            try:    
                await asyncio.wait_for(self.stop_event.wait(), timeout=self.cfg.discovery_interval_s)
            except asyncio.TimeoutError:
                app_logger.debug("Discovery loop waiting complete.")


    async def scheduler_loop(self) -> None:
        """
        Pops due loggers from heap and submits them to fetch pool via a work queue.
        """
        work_q: asyncio.Queue[int] = asyncio.Queue()

        workers = [
            asyncio.create_task(self.fetch_worker_loop(work_q))
            for _ in range(self.cfg.worker_count)
        ]

        try:
            while not self.stop_event.is_set():
                item = await self._pop_due()
                if item is None:
                    # no scheduled loggers
                    try:
                        await asyncio.wait_for(self.stop_event.wait(), timeout=self.cfg.scheduler_tick_s)
                    except asyncio.TimeoutError:
                        pass
                    continue

                due_at, logger_id = item
                now = ts_now()
                if due_at > now:
                    # sleep until due or stop
                    try:
                        await asyncio.wait_for(self.stop_event.wait(), timeout=(due_at - now))
                        break
                    except asyncio.TimeoutError:
                        pass

                await work_q.put(logger_id)

        finally:
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)


    async def fetch_worker_loop(self, work_q: asyncio.Queue[int]) -> None:
        while True:
            logger_id = await work_q.get()
            try:
                device = self.devices.get(logger_id)
                if not device:
                    continue
                
                async with device.schedule.lock:
                    device.schedule.in_flight = True
                    await self._fetch_one(device)

            except Exception as e:
                app_logger.warning(f"Error during fetch worker loop: {e}")
                if logger_id in self.devices:
                    self.devices[logger_id].schedule.inc_error()

            finally:
                if logger_id in self.devices:
                    d = self.devices[logger_id]
                      
                    # reschedule based on updated success/error state
                    d.schedule._update_due_at()
                    await self._reschedule(d)

                work_q.task_done()


    async def _fetch_one(self, device: Device) -> None:
        since = device.schedule.last_seen
        try:
            samples, last_seen = await self.sdg.fetch_samples(device.lookup_id, since=since)

            if samples and last_seen:
                device.schedule.last_seen = last_seen
                device.schedule.add_successful_tx(last_seen)
                
                model_channel_tags = device.get_channel_tags()
                lb = LoggerBatch(
                    logger_id=device.id,
                    last_seen=last_seen,
                    signal_type=SignalType.NB_IOT
                )
                
                # Extract latest values
                # last_values, last_seen = self._extract_last_values(samples)
                # Basically reads samples[0], possibly if len > 1, checks that its sorted DESC
                
                # lb.last_values = last_values
                # lb.last_seen = last_seen
                
                voltages = []
                # Iterate over json and extract values by tag
                for s in samples:
                    dt = s.get("Time")
                    ts = str_to_ts(dt)

                    for tag in model_channel_tags:
                        channel_id = device.channel_id_by_tag.get(tag)
                        
                        if not channel_id:
                            # This channel is probably never created. Check intab API and likely create it
                            channel_id = await self.intab.get_channel_id_or_none(device.id, tag)

                            if not channel_id:
                                channel = await self.intab.create_channel(device.id, tag)
                                channel_id = channel.id
                                device.add_new_channel(channel_id, tag)  # Update Device state with new channel

                        value = s.get(tag)
                        if value is None:
                            raise KeyError()
                        
                        sample = Sample(
                            channel_id=channel_id,
                            value=value,
                            ts=ts
                        )
                        
                        lb.samples.append(sample)
                    
                    v = s.get("Battery Voltage")
                    if v:
                        voltages.append(v)
                    
                    signal_value = s.get("signalStrength")
                    if signal_value:
                        ls = LoggerSignal(ts=ts, value=signal_value)
                        lb.signals.append(ls)
                
                # Add battery voltage
                try:
                    v_mean = statistics.fmean(voltages)
                    lb.battery = v_mean
                except Exception as e:
                    pass
                
                # add LoggerBatch to out queue
                await self.publish_queue.put(lb)

            else:
                device.schedule.inc_error()

        except Exception as e:
            app_logger.warning(f"Error while fetching or extracting data from samples: {e}")


    async def _pop_due(self) -> Optional[tuple[int, int]]:
        async with self.heap_lock:
            while self.heap:
                due_at, logger_id, gen = heapq.heappop(self.heap)
                logger = self.devices.get(logger_id)
                if logger is None:
                    continue
                if gen != logger.schedule.generation:
                    continue  # stale entry
                return (due_at, logger_id)
            return None
        
    async def _push_back(self, logger_id: int) -> None:
        device = self.devices.get(logger_id)
        if not device:
            return
        async with self.heap_lock:
            self._push_logger_to_heap(device=device)

    
    async def _reschedule(self, device: Device) -> None:
        device.schedule.generation += 1
        
        async with self.heap_lock:
            self._push_logger_to_heap(device=device)


    async def _merge_loggers(self, loggers: list[dict]) -> None:
        now = ts_now()
        added = 0
        fetched_ids: set[int] = set()
        for l in loggers:
            logger_id: int = l["id"]
            fetched_ids.add(logger_id)
            if logger_id in self.devices:
                continue  

            # Add new loggers to loggers map
            logger = self._initiate_logger(l, now)
            self.devices[logger.id] = logger
            self.unique_device_ids.add(logger_id)
            
            async with self.heap_lock:
                self._push_logger_to_heap(logger)
            
            added += 1
        
        # compare sets to find deactivated devices
        deactived_ids = self.unique_device_ids.difference(fetched_ids)
        
        # Dont retrieve data from deactivated devices?
        if deactived_ids:
            # delete devices from self.devices?
            pass  
        
        if added:
            print(f"Discovery loop added {added} new logger(s)")


    def _push_logger_to_heap(self, device: Device) -> None:
        heapq.heappush(
            self.heap, (
                device.schedule.due_at,
                device.id,  # logger_id
                device.schedule.generation,
            )
        )

    def _initiate_logger(self, logger: dict, due_at: int|None = None):
        logger_id: int = logger["id"]
        lookup_id: int = logger["lookup_id"]
        logger_model: str = logger["tag"]
        last_seen: int = logger["last_seen"]

        
        logger_channels = logger.get("channels")
        if not isinstance(logger_channels, list):
            raise KeyError()
        
        channels = []
        for ch in logger_channels:
            channel_id = ch["id"]
            channel_tag = ch["tag"]
            channels.append(Channel(id=channel_id, tag=channel_tag))

        return Device(
            id=logger_id,
            lookup_id=lookup_id,
            model=logger_model,
            channels=channels if channels else [],
            schedule=ScheduleState(
                due_at=due_at if due_at is not None else ts_now(),
                last_seen=last_seen
            )
        )
        
    async def nats_publisher_loop(self) -> None:
        buf: list[LoggerBatch] = []
        last_flush = ts_now()
        while not self.stop_event.is_set():
            try:
                item = await asyncio.wait_for(self.publish_queue.get(), timeout=1.0)
                buf.append(item)
                self.publish_queue.task_done()
            except asyncio.TimeoutError:
                pass

            if len(buf) >= 200 or (ts_now() - last_flush) >= 2:
                await self.nats.publish_batch(buf)  # protobuf serialize inside
                buf.clear()
                last_flush = ts_now()


    async def run(self) -> None:
        await self.startup()

        tasks = [
            asyncio.create_task(self.discovery_loop(), name="discovery"),
            asyncio.create_task(self.scheduler_loop(), name="scheduler"),
            asyncio.create_task(self.nats_publisher_loop(), name="publisher"),
        ]

        try:
            await self.stop_event.wait()
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        self.stop_event.set()
        await self.http_client.aclose()
