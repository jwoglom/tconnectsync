import logging
import arrow

from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...eventparser.json_events import PumpStatusSnapshot
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

    # The pump's status goes up as two kinds of devicestatus document, each
    # from the newest event of its type. They are told apart in Nightscout by
    # the field only that kind carries, so the "last uploaded" check of one
    # never holds back the other: the status snapshot stops overnight while
    # the daily basal event keeps coming every ten minutes.
    DAILY_BASAL_FIELD = "pump.battery.voltage"
    STATUS_SNAPSHOT_FIELD = "pump.reservoir"

    def process(self, events: Iterable, time_start: arrow.Arrow, time_end: arrow.Arrow) -> List[dict]:
        events = sorted(events, key=lambda x: (x.raw.timestamp, x.raw.seqNum))

        ns_entries = []
        for event_type, has_field, to_nsentry in (
            (eventtypes.LidDailyBasal, self.DAILY_BASAL_FIELD, self.daily_basal_to_nsentry),
            (PumpStatusSnapshot, self.STATUS_SNAPSHOT_FIELD, self.status_snapshot_to_nsentry),
        ):
            of_type = [event for event in events if isinstance(event, event_type)]
            if not of_type:
                logger.info("ProcessDeviceStatus: No %s event found (time range: %s - %s)" % (event_type.__name__, time_start, time_end))
                continue

            event = self.newest_after_last_upload(of_type, has_field, time_start, time_end)
            if not event:
                continue

            logger.info("ProcessDeviceStatus: newest %s=%s" % (event_type.__name__, event))
            entry = to_nsentry(event)
            if entry is not None:
                ns_entries.append(entry)

        return ns_entries

    def newest_after_last_upload(self, events: List, has_field: str, time_start: arrow.Arrow, time_end: arrow.Arrow):
        """The newest of the events (one type, sorted oldest first) when it is
        newer than the last devicestatus of its kind in Nightscout, else None."""
        logger.debug("ProcessDeviceStatus: querying for last uploaded devicestatus with %s" % has_field)
        last_upload = self.nightscout.last_uploaded_devicestatus(time_start=time_start, time_end=time_end, has_field=has_field)
        last_upload_time = None
        if last_upload:
            last_upload_time = arrow.get(last_upload["created_at"])
        logger.info("ProcessDeviceStatus: Last Nightscout devicestatus upload with %s: %s" % (has_field, last_upload_time))

        newest = events[-1]
        if last_upload_time and newest.raw.timestamp <= last_upload_time:
            if self.pretend:
                logger.info("ProcessDeviceStatus: Skipping %s not after last upload time: %s (time range: %s - %s)" % (type(newest), newest, time_start, time_end))
            return None
        return newest

    def daily_basal_to_nsentry(self, event: eventtypes.LidDailyBasal) -> Optional[dict]:
        # The pump-logs endpoint only returns event 81 (LID_DAILY_BASAL) when no
        # eventIds filter is sent, which is why DEVICE_STATUS implies
        # fetch_all_event_types.
        #
        # Field names follow Tandem's pump-logs JSON: abc is the pump's own
        # state-of-charge byte, already scaled 0-100, and liPoMV is the LiPo
        # voltage in mV. If the event arrived without abc (an event shape we
        # can't yet parse), skip it rather than emit a bogus device status.
        # iob is the pump's own insulin on board, in units; it is left out
        # only when the event has none, never when it is 0.
        if event.abc is None:
            logger.warning("ProcessDeviceStatus: skipping daily basal event missing battery data: %s" % event)
            return None

        return NightscoutEntry.devicestatus(
            created_at=event.eventTimestamp.isoformat(),
            batteryVoltage=(float(event.liPoMV or 0)/1000),
            batteryPercent=int(event.abc),
            pump_event_id = "%s" % event.seqNum,
            iob=event.iob
        )

    def status_snapshot_to_nsentry(self, event: PumpStatusSnapshot) -> Optional[dict]:
        # insulin is what is left in the cartridge, in units. Without it there
        # is nothing to say (the battery already goes up with the daily basal
        # event); 0 is a value and is uploaded.
        if event.insulin is None:
            logger.warning("ProcessDeviceStatus: skipping status snapshot event missing insulin: %s" % event)
            return None

        return NightscoutEntry.devicestatus_reservoir(
            created_at=event.eventTimestamp.isoformat(),
            reservoir=event.insulin,
            batteryPercent=event.abc,
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
