import time
from datetime import datetime, timezone


def sdg_time_to_str(dt: datetime | None = None, ts: int | None = None) -> str:
    """
    Takes a datetime OR unix timestamp. If neither is gived it uses current time
    Return a str as YYYY-MM-DD hh:mm, the format SDG requests.
    """
    if dt is not None and ts is not None:
        raise ValueError("Provide either dt or ts, not both")

    if dt is not None:
        t = dt.astimezone(timezone.utc)
    elif ts is not None:
        t = datetime.fromtimestamp(ts, tz=timezone.utc)
    else:
        t = datetime.now(timezone.utc)
        
    return t.strftime("%Y-%m-%d %H:%M")

def dt_now_isostr() -> str:
    return datetime.now(timezone.utc).isoformat()

def ts_now() -> int:
    return int(time.time())

def str_to_ts(s: str) -> int:
    """
    Convert an isoformatted datestring to unix timestamp in seconds as int
    """
    dt = datetime.fromisoformat(s)
    return int(dt.timestamp())

def ts_to_isostr(ts: int) -> str:
    """
    Convert unix timestamp in seconds to isostring.
    """
    dt = datetime.fromtimestamp(ts)
    return dt.isoformat()

def clamp(value: int, lower: int, upper: int) -> int:
    return min(max(value, lower), upper)
