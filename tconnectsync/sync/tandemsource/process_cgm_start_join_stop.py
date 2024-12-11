import logging
import arrow

from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from ...parser.nightscout import (
    CGM_START_EVENTTYPE,
    CGM_JOIN_EVENTTYPE,
    CGM_STOP_EVENTTYPE,
    NightscoutEntry
)

logger = logging.getLogger(__name__)

class ProcessCGMStartJoinStop:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self):
        return features.PUMP_EVENTS in self.features or features.CGM_ALERTS in self.features

    def process(self, events, time_start, time_end):
        last_upload = None
        last_upload_time = None
        for eventtype in [CGM_START_EVENTTYPE, CGM_JOIN_EVENTTYPE, CGM_STOP_EVENTTYPE]:
            logger.debug("ProcessCGMStartJoinStop: querying for last uploaded entry for %s" % eventtype)
            _last_upload = self.nightscout.last_uploaded_entry(eventtype, time_start=time_start, time_end=time_end)
            _last_upload_time = None
            if _last_upload:
                _last_upload_time = arrow.get(_last_upload["created_at"])

                if not last_upload_time:
                    last_upload = _last_upload
                    last_upload_time = _last_upload_time
                elif _last_upload_time > last_upload_time:
                    last_upload = _last_upload
                    last_upload_time = _last_upload_time
            logger.info("ProcessCGMStartJoinStop: Last Nightscout %s upload: %s" % (eventtype, _last_upload_time))
        logger.info("ProcessCGMStartJoinStop: Overall last Nightscout upload: %s %s" % (last_upload_time, last_upload))

        allEvents = []
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            if last_upload_time and arrow.get(event.eventTimestamp) <= last_upload_time:
                if self.pretend:
                    logger.info("ProcessCGMStartJoinStop: Skipping %s not after last upload time: %s (time range: %s - %s)" % (type(event), event, time_start, time_end))
                continue

            allEvents.append(event)

        allEvents.sort(key=lambda e: e.eventTimestamp)

        ns_entries = []
        for event in allEvents:
            ns_entries.append(self.to_nsentry(event))

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

    def to_nsentry(self, event):
        if type(event) in EventClass._CGM_START:
            return NightscoutEntry.cgm_start(
                created_at = event.eventTimestamp.format(),
                reason = "CGM Session Started",
                pump_event_id = "%s" % event.seqNum
            )
        elif type(event) in EventClass._CGM_JOIN:
            return NightscoutEntry.cgm_join(
                created_at = event.eventTimestamp.format(),
                reason = "CGM Session Joined",
                pump_event_id = "%s" % event.seqNum
            )
        elif type(event) in EventClass._CGM_STOP:
            return NightscoutEntry.cgm_stop(
                created_at = event.eventTimestamp.format(),
                reason = "CGM Session Stopped",
                pump_event_id = "%s" % event.seqNum
            )
