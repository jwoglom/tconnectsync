import logging
import arrow
from tconnectsync.util.time import format_datetime
from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from ...parser.nightscout import (
    EXERCISE_EVENTTYPE,
    SLEEP_EVENTTYPE,
    NightscoutEntry
)

from typing import Iterable, List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from ...api import TConnectApi
    from ...nightscout import NightscoutApi
    from ...eventparser.raw_event import BaseEvent

logger = logging.getLogger(__name__)

class ProcessDeviceStatus:
    def __init__(self, tconnect: "TConnectApi", nightscout: "NightscoutApi", tconnect_device_id: str, pretend: bool, features: List[str] = DEFAULT_FEATURES) -> None:
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self) -> bool:
        return features.DEVICE_STATUS in self.features

    def process(self, events: Iterable, time_start: arrow.Arrow, time_end: arrow.Arrow) -> List[dict]:
        logger.debug("ProcessDeviceStatus: querying for last uploaded devicestatus")
        last_upload = self.nightscout.last_uploaded_devicestatus(time_start=time_start, time_end=time_end)
        last_upload_time = None
        if last_upload:
            last_upload_time = arrow.get(last_upload["created_at"])
        logger.info("ProcessDeviceStatus: Last Nightscout devicestatus upload: %s" % last_upload_time)


        last_daily_basal_event = None
        for event in sorted(events, key=lambda x: x.raw.timestamp):
            if last_upload_time and event.raw.timestamp <= last_upload_time:
                if self.pretend:
                    logger.info("ProcessDeviceStatus: Skipping %s not after last upload time: %s (time range: %s - %s)" % (type(event), event, time_start, time_end))
                continue

            if isinstance(event, eventtypes.LidDailyBasal):
                last_daily_basal_event = event


        if not last_daily_basal_event:
            logger.info("ProcessDeviceStatus: No last_daily_basal_event found for add (time range: %s - %s)" % (time_start, time_end))
            return []

        logger.info("ProcessDeviceStatus: last_daily_basal_event=%s" % (last_daily_basal_event))

        entry = self.daily_basal_to_nsentry(last_daily_basal_event)
        if entry is None:
            return []
        return [entry]

    def daily_basal_to_nsentry(self, event: "BaseEvent") -> Optional[dict]:
        # NOTE: the pump-logs endpoint does not emit event 81 (LID_DAILY_BASAL)
        # for either t:slim X2 or Mobi (verified against live accounts), and no
        # other returned event carries battery data. DEVICE_STATUS therefore
        # yields nothing on the new API; this path stays for the binary decoder
        # and in case the endpoint starts returning event 81.
        #
        # The battery percent is derived from the msb/lsb raw fields; if the
        # event arrived without them (an event shape we can't yet parse), skip
        # it rather than raise on the arithmetic below.
        print("EVENT",event)
        if event.batterylipomillivolts == None or event.batterychargepercent is None:
            logger.warning("ProcessDeviceStatus: skipping daily basal event missing battery data: %s" % event)
            return None

        return NightscoutEntry.devicestatus(
            created_at=format_datetime(event.eventTimestamp),
            batteryVoltage=(float(event.batterylipomillivolts or 0)/1000),
            batteryPercent=event.batterychargepercent,
            pump_event_id = "%s" % event.seqNum
        )


    def write(self, ns_entries: List[dict]) -> int:
        count = 0
        for entry in ns_entries:
            if self.pretend:
                logger.info("Would upload devicestatus to Nightscout: %s" % entry)
            else:
                logger.info("Uploading devicestatus to Nightscout: %s" % entry)
                self.nightscout.upload_entry(entry, entity='devicestatus')
            count += 1

        return count
