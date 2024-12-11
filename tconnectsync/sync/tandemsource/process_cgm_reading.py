import logging
import arrow

from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser.raw_event import TANDEM_EPOCH
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from ...parser.nightscout import (
    CGM_START_EVENTTYPE,
    NightscoutEntry
)

logger = logging.getLogger(__name__)

class ProcessCGMReading:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self):
        return features.CGM in self.features

    def process(self, events, time_start, time_end):
        logger.debug("ProcessCGMReading: querying for last uploaded entry")
        last_upload = self.nightscout.last_uploaded_bg_entry(time_start=time_start, time_end=time_end)
        last_upload_time = None
        if last_upload and "dateString" in last_upload:
            last_upload_time = arrow.get(last_upload["dateString"])
        elif last_upload and "date" in last_upload:
            last_upload_time = arrow.get(last_upload["date"])
        logger.info("ProcessCGMReading: Last Nightscout bg upload: %s" % last_upload_time)

        readings = []
        for event in sorted(events, key=lambda x: self.timestamp_for(x)):
            if last_upload_time and self.timestamp_for(event) <= last_upload_time:
                if self.pretend:
                    logger.info("ProcessCGMReading: Skipping %s not after last upload time: %s (time range: %s - %s)" % (type(event), event, time_start, time_end))
                continue

            readings.append(event)

        ns_entries = []
        for event in readings:
            ns_entries.append(self.to_nsentry(event))

        return ns_entries

    def write(self, ns_entries):
        count = 0
        for entry in ns_entries:
            if self.pretend:
                logger.info("Would upload to Nightscout: %s" % entry)
            else:
                logger.info("Uploading to Nightscout: %s" % entry)
                self.nightscout.upload_entry(entry, entity='entries')
            count += 1

        return count

    def timestamp_for(self, event):
        # For backfills the time the event was added to the pump's event store
        # might not be the time it actually occurred, so we use the egvTimestamp
        return arrow.get(TANDEM_EPOCH + event.egvTimestamp)

    def to_nsentry(self, event):
        return NightscoutEntry.entry(
            sgv = event.currentglucosedisplayvalue,
            created_at = self.timestamp_for(event).format(),
            pump_event_id = "%s" % event.seqNum,
        )
