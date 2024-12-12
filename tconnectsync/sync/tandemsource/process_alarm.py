import logging
import arrow

from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from ...parser.nightscout import (
    ALARM_EVENTTYPE,
    NightscoutEntry
)

logger = logging.getLogger(__name__)

class ProcessAlarm:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self):
        return features.PUMP_EVENTS in self.features

    def process(self, events, time_start, time_end):
        logger.debug("ProcessAlarm: querying for last uploaded alarm")
        last_upload = self.nightscout.last_uploaded_entry(ALARM_EVENTTYPE, time_start=time_start, time_end=time_end)
        last_upload_time = None
        if last_upload:
            last_upload_time = arrow.get(last_upload["created_at"])
        logger.info("Last Nightscout alarm upload: %s" % last_upload_time)

        ns_entries = []
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            if last_upload_time and arrow.get(event.eventTimestamp) <= last_upload_time:
                if self.pretend:
                    logger.info("Skipping Alarm event not after last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
                continue

            if self.skip_event(event):
                continue

            ns_entries.append(self.alarm_to_nsentry(event))


        return ns_entries

    def skip_event(self, event):
        return event.alarmid in (
            eventtypes.LidAlarmActivated.AlarmidEnum.ResumePumpAlarm,
            eventtypes.LidAlarmActivated.AlarmidEnum.ResumePumpAlarm2
        )

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


    def alarm_to_nsentry(self, event):
        if type(event) == eventtypes.LidAlarmActivated:
            return NightscoutEntry.alarm(
                created_at = event.eventTimestamp.format(),
                reason = "%s" % event.alarmid.name,
                pump_event_id = "%s" % event.seqNum
            )
        elif type(event) == eventtypes.LidMalfunctionActivated:
            return NightscoutEntry.alarm(
                created_at = event.eventTimestamp.format(),
                reason = "Malfunction",
                pump_event_id = "%s" % event.seqNum
            )
