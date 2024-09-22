import logging
import arrow

from ...features import DEFAULT_FEATURES
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from ...parser.nightscout import (
    BASALSUSPENSION_EVENTTYPE,
    NightscoutEntry
)

logger = logging.getLogger(__name__)

class ProcessBasalSuspension:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def process(self, events, time_start, time_end):
        logger.debug("ProcessBasalSuspension: querying for last uploaded suspension")
        last_upload = self.nightscout.last_uploaded_entry(BASALSUSPENSION_EVENTTYPE, time_start=time_start, time_end=time_end)
        last_upload_time = None
        if last_upload:
            last_upload_time = arrow.get(last_upload["created_at"])
        logger.info("Last Nightscout basalsuspension upload: %s" % last_upload_time)

        ns_entries = []
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            if last_upload_time and arrow.get(event.eventTimestamp) < last_upload_time:
                if self.pretend:
                    logger.info("Skipping basalsuspension event before last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
                continue

            ns_entries.append(self.suspension_to_nsentry(event))


        return ns_entries

    def write(self, ns_entries):
        count = 0
        for entry in ns_entries:
            if self.pretend:
                logger.info("Would upload to Nightscout: %s" % entry)
            else:
                logger.info("Uploading to Nightscout: %s" % entry)
                self.nightscout.upload_entry(entry)
            count += 1

        return count


    def suspension_to_nsentry(self, event):
        if type(event) == eventtypes.LidPumpingSuspended:
            return NightscoutEntry.basalsuspension(
                created_at = event.eventTimestamp,
                reason = ', '.join(bitmask_to_list(event.suspendreason))
            )