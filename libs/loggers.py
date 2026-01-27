from typing import Optional
from collections import deque
from statistics import median, StatisticsError

from libs.helpers import ts_now, clamp


MAX_TRANSMISSION_INTERVAL = 3600
MIN_TRANSMISSION_INTERVAL = 900
POSTPONE = 60
BACKOFF = 10
LOGGER_TX_DELAY = 20




class Channel:
    id: int
    # lookup_id: int
    tag: str

    def __init__(self, id: int, tag: str):
        self.id = id
        self.tag = tag

class LoggerState:
    due_at: int     # unix timestamp
    last_seen: int  # unix timestamp, request history from this date
    interval: Optional[int]
    tx_history: deque
    generation: int  # bump when rescheduling: to ignore stale heap entries
    in_flight: bool
    errors: int
    
    def __init__(self, last_seen: int, due_at=ts_now(), maxlen=5):
        self.due_at = due_at
        self.last_seen = last_seen
        self.tx_history = deque(maxlen=maxlen)
        self.generation = 0
        self.in_flight = False
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


class Logger:
    id: int         # ID in intabcloud
    lookup_id: int  # also serial/IMEI in SDG
    model: str      # used to resolve possible channel tags
    channels: list[Channel]
    channel_id_by_tag: dict[str, int]
    state: LoggerState

    def __init__(
            self, 
            id: int, 
            lookup_id: int, 
            tag: str, 
            state: LoggerState, 
            channels: list[Channel]
    ) -> None:

        self.id = id
        self.lookup_id = lookup_id
        self.tag = tag
        self.channels = channels
        self.state = state

        channel_map = dict()
        for ch in channels:
            channel_map[ch.tag] = ch.id
        
        self.channel_id_by_tag = channel_map
    
    def get_channel_tags(self) -> list[str]:
        return [ch for ch in self.channel_id_by_tag.keys()]

