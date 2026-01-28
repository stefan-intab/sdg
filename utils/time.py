import time
from datetime import datetime


def ts_now() -> int:
    return int(time.time())

def str_to_ts(s: str) -> int:
    """
    Convert an isoformatted datestring to unix timestamp in seconds as int
    """
    dt = datetime.fromisoformat(s)
    return int(dt.timestamp())


def clamp(
    value: int, lower: int, upper: int) -> int:
    return min(max(value, lower), upper)