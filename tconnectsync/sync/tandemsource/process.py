import logging
import collections

from ...features import DEFAULT_FEATURES
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from .process_basal import ProcessBasal
from .process_basal_suspension import ProcessBasalSuspension
from .process_basal_resume import ProcessBasalResume
from .process_alarm import ProcessAlarm

logger = logging.getLogger(__name__)

class ProcessTimeRange:
    def __init__(self, tconnect, nightscout, tconnectDevice, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnectDevice['tconnectDeviceId']
        self.max_date_with_events = tconnectDevice['maxDateWithEvents']
        self.pretend = pretend
        self.features = features

    event_classes = {
        EventClass.BASAL.name: ProcessBasal,
        EventClass.BASAL_SUSPENSION.name: ProcessBasalSuspension,
        EventClass.BASAL_RESUME.name: ProcessBasalResume,
        EventClass.ALARM.name: ProcessAlarm
    }

    def process(self, time_start, time_end):
        logger.info(f"ProcessTimeRange {time_start=} {time_end=} {self.tconnect_device_id=} {self.features=}")

        pump_events_raw = self.tconnect.tandemsource.pump_events_raw(self.tconnect_device_id, time_start, time_end)
        pump_events_decoded = decode_raw_events(pump_events_raw)
        logger.info(f"Read {len(pump_events_decoded)=} (est. {len(pump_events_decoded)/EVENT_LEN} events)")
        events = Events(pump_events_decoded)

        events_first_time = None
        events_last_time = None
        for_eventclass = collections.defaultdict(list)
        for event in events:
            if not events_first_time:
                events_first_time = event.eventTimestamp
            if not events_last_time:
                events_last_time = event.eventTimestamp
            events_first_time = min(events_first_time, event.eventTimestamp)
            events_last_time = max(events_last_time, event.eventTimestamp)

            clazz = EventClass.for_event(event)
            if clazz:
                processed_count += 1
                for_eventclass[clazz.name].append(event)

        count_by_eventclass = {k: len(v) for k,v in for_eventclass.items()}
        logger.info(f"Found events: {count_by_eventclass}")

        processed_count = 0
        for clazz, events in for_eventclass.items():
            if clazz in self.event_classes.keys():
                c = self.event_classes[clazz](self.tconnect, self.nightscout, self.tconnect_device_id, self.pretend, self.features)
                ns_entries = c.process(events, events_first_time, events_last_time)
                processed_count += c.write(ns_entries)


        return processed_count

