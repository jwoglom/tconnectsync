import logging
import collections
import arrow

from types import ModuleType
from typing import Dict, Iterable, List, Optional, Protocol, Tuple, Type, TYPE_CHECKING
if TYPE_CHECKING:
    from ...api import TConnectApi
    from ...nightscout import NightscoutApi
    from ...api.tandemsource import BffPump

class EventProcessor(Protocol):
    """Structural interface implemented by every Process* event handler."""
    def __init__(self, tconnect: "TConnectApi", nightscout: "NightscoutApi", tconnect_device_id: str, pretend: bool, features: List[str]) -> None: ...
    def enabled(self) -> bool: ...
    def process(self, events: Iterable, time_start: arrow.Arrow, time_end: arrow.Arrow) -> List[dict]: ...
    def write(self, ns_entries: List[dict]) -> int: ...

from ...features import DEVICE_STATUS, DEFAULT_FEATURES
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from .process_basal import ProcessBasal
from .process_basal_suspension import ProcessBasalSuspension
from .process_basal_resume import ProcessBasalResume
from .process_alarm import ProcessAlarm
from .process_bolus import ProcessBolus
from .process_cartridge import ProcessCartridge
from .process_cgm_alert import ProcessCGMAlert
from .process_cgm_start_join_stop import ProcessCGMStartJoinStop
from .process_cgm_reading import ProcessCGMReading
from .process_device_status import ProcessDeviceStatus
from .process_user_mode import ProcessUserMode
from .update_profiles import UpdateProfiles

logger = logging.getLogger(__name__)

class ProcessTimeRange:
    def __init__(self, tconnect: "TConnectApi", nightscout: "NightscoutApi", tconnectDevice: "BffPump", pretend: bool, secret: ModuleType, features: List[str] = DEFAULT_FEATURES) -> None:
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnectDevice['assignmentId']
        self.max_date_with_events = tconnectDevice.get('maxDateOfEvents')
        self.pretend = pretend
        self.secret = secret
        self.features = features

    event_classes: Dict[str, Type[EventProcessor]] = {
        EventClass.BASAL.name: ProcessBasal,
        EventClass.BASAL_SUSPENSION.name: ProcessBasalSuspension,
        EventClass.BASAL_RESUME.name: ProcessBasalResume,
        EventClass.ALARM.name: ProcessAlarm,
        EventClass.BOLUS.name: ProcessBolus,
        EventClass.CARTRIDGE.name: ProcessCartridge,
        EventClass.CGM_ALERT.name: ProcessCGMAlert,
        EventClass.CGM_START_JOIN_STOP.name: ProcessCGMStartJoinStop,
        EventClass.CGM_READING.name: ProcessCGMReading,
        EventClass.USER_MODE.name: ProcessUserMode,
        EventClass.DEVICE_STATUS.name: ProcessDeviceStatus
    }

    updater_classes = [
        UpdateProfiles
    ]

    def process(self, time_start: arrow.Arrow, time_end: arrow.Arrow) -> Tuple[int, Optional[int]]:
        fetch_all_event_types = self.secret.FETCH_ALL_EVENT_TYPES or DEVICE_STATUS in self.features

        logger.info(f"ProcessTimeRange time_start={time_start} time_end={time_end} tconnect_device_id={self.tconnect_device_id} features={self.features} fetch_all_event_types={fetch_all_event_types}")
        events = self.tconnect.tandemsource.pump_events(self.tconnect_device_id, time_start, time_end, fetch_all_event_types=fetch_all_event_types)

        events_first_time = None
        events_last_time = None
        last_event_seqnum = None
        for_eventclass = collections.defaultdict(list)
        for event in events:
            if not events_first_time:
                events_first_time = event.eventTimestamp
            if not events_last_time:
                events_last_time = event.eventTimestamp
            if not last_event_seqnum:
                last_event_seqnum = event.seqNum
            events_first_time = min(events_first_time, event.eventTimestamp)
            events_last_time = max(events_last_time, event.eventTimestamp)
            last_event_seqnum = max(event.seqNum, last_event_seqnum)

            clazz = EventClass.for_event(event)
            if clazz:
                for_eventclass[clazz.name].append(event)

        count_by_eventclass = {k: len(v) for k,v in for_eventclass.items()}
        logger.info(f"Found events: {count_by_eventclass}")

        processed_count = 0
        for clazz, events in for_eventclass.items():
            if clazz in self.event_classes.keys():
                c = self.event_classes[clazz](self.tconnect, self.nightscout, self.tconnect_device_id, self.pretend, self.features)
                if c.enabled():
                    logger.info("%s is enabled from features %s" % (clazz, self.features))
                    # Cap events_last_time at time_end to handle pump clock drift
                    # Ensure time_end is timezone-aware for comparison
                    time_end_aware = arrow.get(time_end)
                    capped_time_end = min(events_last_time, time_end_aware) if events_last_time else time_end_aware
                    # events_first_time is populated whenever for_eventclass has entries
                    # (i.e. at least one event was seen); fall back to time_start otherwise.
                    time_start_for_events = events_first_time if events_first_time else time_start
                    ns_entries = c.process(events, time_start_for_events, capped_time_end)
                    w = c.write(ns_entries)
                    if w:
                        processed_count += w
                else:
                    logger.info("Skipping %s, is not enabled from features %s" % (clazz, self.features))

        for updater_class in self.updater_classes:
            updater = updater_class(self.tconnect, self.nightscout, self.tconnect_device_id, self.pretend, self.features)
            if updater.enabled():
                logger.info("%s is enabled from features %s" % (updater_class.__name__, self.features))
                done = updater.update(self.pretend)
                logger.info("%s completed with update required: %s" % (updater_class.__name__, done))
            else:
                logger.info("Skipping %s, is not enabled from features %s" % (updater_class.__name__, self.features))

        logger.info("Processed %d events. Last event ID seen: %d" % (processed_count if processed_count else 0, last_event_seqnum if last_event_seqnum else -1))
        return processed_count, last_event_seqnum

