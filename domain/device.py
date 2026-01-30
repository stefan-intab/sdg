from domain.schedule import ScheduleState

from infra.logging_config import app_logger


CHANNEL_TAGS_BY_MODEL = {
    "IOTSU_N3_AQ05": ["CO2", "Humidity", "Temperature"],
    "IOTSU_N3_RHTEMP": ["Humidity", "Temperature"],
}

class Channel:
    id: int
    tag: str

    def __init__(self, id: int, tag: str):
        self.id = id
        self.tag = tag


class Device:
    id: int         # logger.id in intabcloud
    lookup_id: int  # also serial/IMEI in SDG
    model: str      # used to resolve possible channel tags
    channels: list[Channel]
    channel_id_by_tag: dict[str, int]
    schedule: ScheduleState

    def __init__(
            self, 
            id: int, 
            lookup_id: int,
            model: str,
            schedule: ScheduleState, 
            channels: list[Channel]
    ) -> None:

        if not model.upper() in CHANNEL_TAGS_BY_MODEL:
            # Log error
            raise ValueError(f"Unknown logger model: {model}")
            
        self.id = id
        self.lookup_id = lookup_id
        self.model = model.upper()
        self.channels = channels
        self.schedule = schedule

        channel_map = dict()
        for ch in channels:
            channel_map[ch.tag] = ch.id
            
        self.channel_id_by_tag = channel_map
    
    def get_channel_tags(self) -> list[str]:
        tags = CHANNEL_TAGS_BY_MODEL.get(self.model)
        if not tags:
            app_logger.error("Could not extract channel tags by model from device id:", self.id)
            return []
        return tags
    
    def add_new_channel(self, channel_id: int, tag: str) -> None:
        channel = Channel(id=channel_id, tag=tag)
        self.channels.append(channel)
        self.channel_id_by_tag[tag] = channel_id
        
        

