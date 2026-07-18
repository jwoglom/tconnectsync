import logging
import arrow

from typing import Iterable, List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from ...api import TConnectApi
    from ...nightscout import NightscoutApi
    from ...eventparser.raw_event import BaseEvent

from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from tconnectsync.util.time import format_datetime
from ...parser.nightscout import (
    BASALRESUME_EVENTTYPE,
    NightscoutEntry
)

logger = logging.getLogger(__name__)

class ProcessBasalResume:
    def __init__(self, tconnect: "TConnectApi", nightscout: "NightscoutApi", tconnect_device_id: str, pretend: bool, features: List[str] = DEFAULT_FEATURES) -> None:
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self) -> bool:
        return features.PUMP_EVENTS in self.features

    def process(self, events: Iterable, time_start: arrow.Arrow, time_end: arrow.Arrow) -> List[dict]:
        logger.debug("ProcessBasalResume: querying for last uploaded resume-suspension")
        last_upload = self.nightscout.last_uploaded_entry(BASALRESUME_EVENTTYPE, time_start=time_start, time_end=time_end)
        last_upload_time = None
        if last_upload:
            last_upload_time = arrow.get(last_upload["created_at"])
        logger.info("Last Nightscout BasalResume upload: %s" % last_upload_time)

        ns_entries = []
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            if last_upload_time and arrow.get(event.eventTimestamp) <= last_upload_time:
                if self.pretend:
                    logger.info("Skipping BasalResume event not after last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
                continue

            ns_entries.append(self.resume_to_nsentry(event))


        return ns_entries

    def write(self, ns_entries: List[dict]) -> int:
        count = 0
        for entry in ns_entries:
            if self.pretend:
                logger.info("Would upload to Nightscout: %s" % entry)
            else:
                logger.info("Uploading to Nightscout: %s" % entry)
                self.nightscout.upload_entry(entry)
            count += 1

        return count


    def resume_to_nsentry(self, event: "BaseEvent") -> Optional[dict]:
        if type(event) == eventtypes.LidPumpingResumed:
            return NightscoutEntry.basalresume(
                created_at = format_datetime(event.eventTimestamp),
                pump_event_id = "%s" % event.seqNum
            )
