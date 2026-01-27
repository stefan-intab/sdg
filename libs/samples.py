import orjson
from typing import Optional


class Sample:
    def __init__(self, id: int, value: float, ts: int):
        self.channel_id = id
        self.value = value
        self.ts = ts

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "value": self.value,
            "ts": self.ts,
        }

class Device:
    def __init__(
        self,
        id: int,
        last_seen: int,
        signal: float,
        battery: float,
        samples: Optional[list[Sample]] = None,
    ):
        self.logger_id = id
        self.last_seen = last_seen
        self.signal = signal
        self.battery = battery
        self.samples = samples or []

    def to_dict(self) -> dict:
        return {
            "logger_id": self.logger_id,
            "last_seen": self.last_seen,
            "signal": self.signal,
            "battery": self.battery,
            "samples": [s.to_dict() for s in self.samples],
        }


test = {
    "loggers": [
        {
            "id": 1,
            "signal": -82,
            "battery": 3.6,
            "samples": [
                {"id": 101, "value": 21.32, "ts": 115474854},
                {"id": 102, "value": 76.23, "ts": 115474854}
            ]
        }
    ]
    }        




d = Device(id=1, last_seen=545454, signal=-82., battery=3.6, samples=[
    Sample(id=11, value=23.2, ts=1242545)
])

print(d)
print(orjson.dumps(d.to_dict()))
