from typing import Optional
from collections import deque
from statistics import median, StatisticsError
import asyncio

from utils.time import ts_now, clamp
from infra.logging_config import app_logger


MAX_TRANSMISSION_INTERVAL = 3600
MIN_TRANSMISSION_INTERVAL = 900
POSTPONE = 60
BACKOFF = 10
LOGGER_TX_DELAY = 20


class ScheduleState:
    due_at: int     # unix timestamp
    last_seen: int  # unix timestamp, request history from this date
    interval: Optional[int]
    tx_history: deque
    generation: int  # bump when rescheduling: to ignore stale heap entries
    lock: asyncio.Lock
    errors: int
    
    def __init__(self, last_seen: int, due_at: int | None = None, maxlen=5):
        self.due_at = due_at if due_at is not None else ts_now()
        self.last_seen = last_seen
        self.tx_history = deque(maxlen=maxlen)
        self.generation = 0
        self.in_flight = False
        self.lock = asyncio.Lock()
        self.errors = 0
    
    def add_successful_tx(self, ts: int):
        self.tx_history.appendleft(ts)
        self.errors = 0

    def inc_error(self):
        self.errors += 1
    
    def _update_due_at(self):
        if self.errors > 0:
            delay = POSTPONE * (BACKOFF ** (self.errors - 1))
            delay = clamp(int(delay), lower=POSTPONE, upper=MAX_TRANSMISSION_INTERVAL)
            self.due_at = ts_now() + delay + LOGGER_TX_DELAY
            return
        
        # Not enough history to estimate an interval
        if len(self.tx_history) < 2:
            self.interval = MIN_TRANSMISSION_INTERVAL
            self.due_at = ts_now() + self.interval + LOGGER_TX_DELAY
            return

        # More than 2 intervals: calc median
        md = self._calc_median()
        self.interval = clamp(md, MIN_TRANSMISSION_INTERVAL, MAX_TRANSMISSION_INTERVAL)
        self.due_at = self.tx_history[0] + self.interval + LOGGER_TX_DELAY

    def _calc_median(self):
        deltas = []
        length = len(self.tx_history)
        for i in range(length):
            if i < length-1:
                ts1 = self.tx_history[i]
                ts2 = self.tx_history[i+1]
                d = ts1-ts2
                deltas.append(d)
        
        try:
            md = int(median(deltas))
        except StatisticsError:
            md = MIN_TRANSMISSION_INTERVAL
        
        return md
