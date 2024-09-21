import logging

from ...features import DEFAULT_FEATURES
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser import events as eventtypes

logger = logging.getLogger(__name__)

class ProcessTimeRange:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features
    
    def process(self, time_start, time_end):
        logger.info(f"ProcessTimeRange {time_start=} {time_end=} {self.tconnect_device_id=} {self.features=}")

        pump_events_raw = self.tconnect.tandemsource.pump_events_raw(self.tconnect_device_id, time_start, time_end)
        pump_events_decoded = decode_raw_events(pump_events_raw)
        logger.info(f"Read {len(pump_events_decoded)=} (est. {len(pump_events_decoded)/EVENT_LEN} events)")
        events = Events(pump_events_decoded)

        processed_count = 0
        for event in events:
            if isinstance(event, eventtypes.LidBasalRateChange):
                logger.debug(f"Found {event=}")
        

        return processed_count
        