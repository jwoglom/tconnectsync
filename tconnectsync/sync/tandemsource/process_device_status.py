import logging
import arrow

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

logger = logging.getLogger(__name__)

class ProcessDeviceStatus:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self):
        return features.DEVICE_STATUS in self.features

    def process(self, events, time_start, time_end):
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

        ns_entries = []
        ns_entries.append(self.daily_basal_to_nsentry(last_daily_basal_event))
        return ns_entries

    def daily_basal_to_nsentry(self, event):
        return NightscoutEntry.devicestatus(
            created_at=event.eventTimestamp.format(),
            batteryVoltage=(float(event.batterylipomillivolts or 0)/1000),
            batteryPercent=int(100*event.batteryChargePercent),
            pump_event_id = "%s" % event.seqNum
        )


    def write(self, ns_entries):
        count = 0
        for entry in ns_entries:
            if self.pretend:
                logger.info("Would upload devicestatus to Nightscout: %s" % entry)
            else:
                logger.info("Uploading devicestatus to Nightscout: %s" % entry)
                self.nightscout.upload_entry(entry, entity='devicestatus')
            count += 1

        return count
