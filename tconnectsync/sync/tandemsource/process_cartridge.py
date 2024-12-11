import logging
import arrow

from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from ...parser.nightscout import (
    SITECHANGE_EVENTTYPE,
    NightscoutEntry
)

logger = logging.getLogger(__name__)

class ProcessCartridge:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self):
        return features.PUMP_EVENTS in self.features

    def process(self, events, time_start, time_end):
        logger.debug("ProcessCartridge: querying for last uploaded entry")
        last_upload = self.nightscout.last_uploaded_entry(SITECHANGE_EVENTTYPE, time_start=time_start, time_end=time_end)
        last_upload_time = None
        if last_upload:
            last_upload_time = arrow.get(last_upload["created_at"])
        logger.info("Last Nightscout sitechange upload: %s" % last_upload_time)

        cartFilledEvents = []
        cannulaFilledEvents = []
        tubingFilledEvents = []
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            if last_upload_time and arrow.get(event.eventTimestamp) <= last_upload_time:
                if self.pretend:
                    logger.info("Skipping %s not after last upload time: %s (time range: %s - %s)" % (type(event), event, time_start, time_end))
                continue

            if type(event) == eventtypes.LidCartridgeFilled:
                cartFilledEvents.append(event)
            elif type(event) == eventtypes.LidCannulaFilled:
                cannulaFilledEvents.append(event)
            elif type(event) == eventtypes.LidTubingFilled:
                tubingFilledEvents.append(event)

        cartFilledEvents.sort(key=lambda e: e.eventTimestamp)
        cannulaFilledEvents.sort(key=lambda e: e.eventTimestamp)
        tubingFilledEvents.sort(key=lambda e: e.eventTimestamp)

        ns_entries = []
        for cartFilled in cartFilledEvents:
            ns_entries.append(self.cart_to_nsentry(cartFilled))

        for cannulaFilled in cannulaFilledEvents:
            ns_entries.append(self.cannula_to_nsentry(cannulaFilled))

        for tubingFilled in tubingFilledEvents:
            ns_entries.append(self.tubing_to_nsentry(tubingFilled))


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

    def cart_to_nsentry(self, cartFilled):
        return NightscoutEntry.sitechange(
            created_at = cartFilled.eventTimestamp.format(),
            reason = "Cartridge Filled" + (" (%du filled)" % round(cartFilled.v2Volume) if cartFilled.v2Volume else ""),
            pump_event_id = "%s" % cartFilled.seqNum
        )

    def cannula_to_nsentry(self, cannulaFilled):
        return NightscoutEntry.sitechange(
            created_at = cannulaFilled.eventTimestamp.format(),
            reason = "Cannula Filled" + (" (%du primed)" % round(cannulaFilled.primesize, 2) if cannulaFilled.primesize else ""),
            pump_event_id = "%s" % cannulaFilled.seqNum
        )

    def tubing_to_nsentry(self, tubingFilled):
        return NightscoutEntry.sitechange(
            created_at = tubingFilled.eventTimestamp.format(),
            reason = "Tubing Filled" + (" (%du primed)" % round(tubingFilled.primesize) if tubingFilled.primesize else ""),
            pump_event_id = "%s" % tubingFilled.seqNum
        )
