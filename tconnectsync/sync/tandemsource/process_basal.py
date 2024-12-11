import logging
import arrow

from ...secret import IGNORE_ZERO_UNIT_BASAL
from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from .helpers import insulin_float_round, insulin_milliunits_to_real
from ...domain.tandemsource.event_class import EventClass
from ...parser.nightscout import (
    BASAL_EVENTTYPE,
    NightscoutEntry
)

logger = logging.getLogger(__name__)

class ProcessBasal:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self):
        return features.BASAL in self.features

    def process(self, events, time_start, time_end):
        logger.debug("ProcessBasal: querying for last uploaded entry")
        last_upload = self.nightscout.last_uploaded_entry(BASAL_EVENTTYPE, time_start=time_start, time_end=time_end)
        last_upload_time = None
        if last_upload:
            last_upload_time = arrow.get(last_upload["created_at"])
        logger.info("Last Nightscout basal upload: %s" % last_upload_time)

        with_duration = []
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            if last_upload_time and arrow.get(event.eventTimestamp) <= last_upload_time:
                if self.pretend:
                    logger.info("Skipping basal event not after last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
                continue

            with_duration.append([event.eventTimestamp, None, event])

        if not with_duration:
            logger.info("No basal events found to process")
            return []

        for i in range(len(with_duration)-1):
            with_duration[i][1] = with_duration[i+1][0] - with_duration[i][0]

        with_duration[-1][1] = time_end - with_duration[-1][0]

        ns_entries = []
        for item in with_duration:
            ns = self.basal_to_nsentry(*item)
            if ns:
                ns_entries.append(ns)

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


    def basal_to_nsentry(self, start, duration, event):
        if type(event) == eventtypes.LidBasalRateChange:
            value = insulin_float_round(event.commandedbasalrate)
            if IGNORE_ZERO_UNIT_BASAL and value < 0.01:
                logger.info("Ignoring basal entry with %.2f unit basal because IGNORE_ZERO_UNIT_BASAL=true: %s" % (value, event))
                return None
            return NightscoutEntry.basal(
                value = value,
                duration_mins = duration.seconds / 60,
                created_at = start.format(),
                reason = ', '.join(bitmask_to_list(event.changetype)),
                pump_event_id = "%s" % event.seqNum
            )
        if type(event) == eventtypes.LidBasalDelivery:
            value = insulin_milliunits_to_real(event.commandedRate)
            if IGNORE_ZERO_UNIT_BASAL and value < 0.01:
                logger.info("Ignoring basal entry with %.2f unit basal because IGNORE_ZERO_UNIT_BASAL=true: %s" % (value, event))
                return None
            return NightscoutEntry.basal(
                value = value,
                duration_mins = duration.seconds / 60,
                created_at = start.format(),
                reason = ', '.join(bitmask_to_list(event.commandedRateSource)),
                pump_event_id = "%s" % event.seqNum
            )
