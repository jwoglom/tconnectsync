import logging
import arrow
from tconnectsync.util.time import format_datetime
from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from .helpers import insulin_float_round
from ...parser.nightscout import (
    BOLUS_EVENTTYPE,
    NightscoutEntry
)

from typing import Iterable, List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from ...api import TConnectApi
    from ...nightscout import NightscoutApi
    from ...eventparser.raw_event import BaseEvent

logger = logging.getLogger(__name__)

class ProcessBolus:
    def __init__(self, tconnect: "TConnectApi", nightscout: "NightscoutApi", tconnect_device_id: str, pretend: bool, features: List[str] = DEFAULT_FEATURES) -> None:
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self) -> bool:
        return features.BOLUS in self.features

    def process(self, events: Iterable, time_start: arrow.Arrow, time_end: arrow.Arrow) -> List[dict]:
        logger.debug("ProcessBolus: querying for last uploaded entry")
        last_upload = self.nightscout.last_uploaded_entry(BOLUS_EVENTTYPE, time_start=time_start, time_end=time_end)
        last_upload_time = None
        if last_upload:
            last_upload_time = arrow.get(last_upload["created_at"])
        logger.info("Last Nightscout bolus upload: %s" % last_upload_time)

        # Correlate a bolus's request/completion messages by bolusid.
        bolusEventsForId = {}
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            bolusEventsForId.setdefault(event.bolusId, {})[type(event)] = event

        # Emit one Nightscout treatment per completion event, each at its own time:
        #  - LidBolusCompleted -> the standard / "now" bolus (carbs, bg, notes)
        #  - LidBolexCompleted -> the extended portion of a combo bolus (added
        #    separately, insulin only, so its later delivery is not dropped).
        completions = []
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            if type(event) not in (eventtypes.LidBolusCompleted, eventtypes.LidBolexCompleted):
                continue
            if last_upload_time and arrow.get(event.eventTimestamp) <= last_upload_time:
                if self.pretend:
                    logger.info("Skipping bolus completion not after last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
                continue
            completions.append(event)

        completions.sort(key=lambda e: e.eventTimestamp)

        ns_entries = []
        for event in completions:
            if type(event) == eventtypes.LidBolexCompleted:
                ns_entries.append(self.bolex_to_nsentry(event))
                continue

            m = bolusEventsForId[event.bolusId]
            ns_entries.append(self.bolus_to_nsentry(
                event,
                bolusRequested1 = m.get(eventtypes.LidBolusRequestedMsg1),
                bolusRequested2 = m.get(eventtypes.LidBolusRequestedMsg2),
                bolusRequested3 = m.get(eventtypes.LidBolusRequestedMsg3),
            ))

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


    def bolus_to_nsentry(self, bolusCompleted: "BaseEvent", bolusRequested1: "BaseEvent", bolusRequested2: "BaseEvent", bolusRequested3: "BaseEvent") -> Optional[dict]:
        suffixes = []
        if bolusRequested2 and bolusRequested2.userOverride == eventtypes.LidBolusRequestedMsg2.UseroverrideEnum.Yes:
            suffixes.append('(Override)')

        if bolusRequested2 and bolusRequested2.declinedCorrection == eventtypes.LidBolusRequestedMsg2.DeclinedcorrectionEnum.Yes:
            suffixes.append('(Declined Correction)')

        suffix = (' ' + (' '.join(suffixes))) if suffixes else ''

        seq_nums = []
        for e in [bolusCompleted, bolusRequested1, bolusRequested2, bolusRequested3]:
            if e:
                seq_nums.append(str(e.seqNum))

        notes = ''
        if bolusRequested2 and str(bolusRequested2.optionsRaw) in eventtypes.LidBolusRequestedMsg2.OptionsMap:
            notes = eventtypes.LidBolusRequestedMsg2.OptionsMap['%d' % bolusRequested2.optionsRaw]


        return NightscoutEntry.bolus(
            bolus = insulin_float_round(bolusCompleted.insulinDelivered),
            carbs = bolusRequested1.carbAmount if bolusRequested1 and bolusRequested1.carbAmount>0 else None,
            created_at = format_datetime(bolusCompleted.eventTimestamp),
            notes = notes + suffix,
            bg = bolusRequested1.bg if bolusRequested1 and bolusRequested1.bg > 0 else None,
            pump_event_id = ",".join(seq_nums)
        )

    def bolex_to_nsentry(self, bolexCompleted: "BaseEvent") -> Optional[dict]:
        # The extended portion of a combo bolus, added as its own treatment at
        # the time it finished delivering. Insulin only; carbs/bg belong to the
        # initial LidBolusCompleted entry and must not be double-counted here.
        return NightscoutEntry.bolus(
            bolus = insulin_float_round(bolexCompleted.insulinDelivered),
            carbs = None,
            created_at = format_datetiem(bolexCompleted.eventTimestamp),
            notes = "Extended Bolus",
            bg = None,
            pump_event_id = "%s" % bolexCompleted.seqNum
        )
