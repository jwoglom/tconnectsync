import arrow
import logging
from tconnectsync.domain.bolus import Bolus

from tconnectsync.sync.cgm import find_event_at

from ..parser.nightscout import (
    BOLUS_EVENTTYPE,
    NightscoutEntry
)
from ..parser.tconnect import TConnectEntry
from ..secret import SKIP_NS_LAST_UPLOADED_CHECK

logger = logging.getLogger(__name__)

"""
Given bolus data input from the therapy timeline CSV, converts it into a digestable format.
"""
def process_bolus_events(bolusdata, cgmEvents=None, source=""):
    bolusEvents = []

    for b in bolusdata:
        parsed = None
        if source == "ciq":
            parsed = b.to_bolus()
        else:
            parsed = TConnectEntry.parse_bolus_entry(b)
        
        assert type(parsed) == Bolus
        if parsed.completion != "Completed":
            if parsed.insulin and float(parsed.insulin) > 0:
                # Count non-completed bolus if any insulin was delivered (vs. the amount of insulin requested)
                parsed.description += " (%s: requested %s units)" % (parsed.completion, parsed.requested_insulin)
            else:
                logger.warning("Skipping non-completed %s bolus data (was a bolus in progress?): %s parsed: %s" % (source, b, parsed))
                continue

        if parsed.bg and cgmEvents:
            requested_at = parsed.request_time if not parsed.extended_bolus else parsed.bolex_start_time
            parsed.bg_type = guess_bolus_bg_type(parsed.bg, requested_at, cgmEvents)

        bolusEvents.append(parsed)

    bolusEvents.sort(key=lambda event: arrow.get(event.request_time if not event.is_extended_bolus else event.bolex_start_time))

    return bolusEvents

"""
Determine whether the given BG specified in the bolus is identical to the
most recent CGM reading at that time. If it is, return SENSOR.
Otherwise, return FINGER.
"""
def guess_bolus_bg_type(bg, created_at, cgmEvents):
    if not cgmEvents:
        return NightscoutEntry.FINGER

    event = find_event_at(cgmEvents, created_at)
    if event and str(event["bg"]) == str(bg):
        return NightscoutEntry.SENSOR
    
    return NightscoutEntry.FINGER


"""
Given processed bolus data, adds bolus events to Nightscout.
"""
def ns_write_bolus_events(nightscout, bolusEvents, pretend=False, include_bg=False, reading_events=None, time_start=None, time_end=None):
    logger.debug("ns_write_bolus_events: querying for last uploaded entry")
    last_upload = nightscout.last_uploaded_entry(BOLUS_EVENTTYPE, time_start=time_start, time_end=time_end)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    logger.info("Last Nightscout bolus upload: %s" % last_upload_time)

    if SKIP_NS_LAST_UPLOADED_CHECK:
        logger.warning("Overriding last upload check")
        last_upload = None
        last_upload_time = None

    add_count = 0
    for event in bolusEvents:
        created_at = event.completion_time if not event.is_extended_bolus else event.bolex_start_time
        if last_upload_time and arrow.get(created_at) <= last_upload_time:
            if pretend:
                logger.info("Skipping basal event before last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
            continue

        if include_bg and event.bg:
            entry = NightscoutEntry.bolus(
                bolus=event.insulin,
                carbs=event.carbs,
                created_at=created_at,
                notes="{}{}{}".format(event.description, " (Override)" if event.user_override == "1" else "", " (Extended)" if event.extended_bolus == "1" else ""),
                bg=event.bg,
                bg_type=event.bg_type
            )
        else:
            entry = NightscoutEntry.bolus(
                bolus=event.insulin,
                carbs=event.carbs,
                created_at=created_at,
                notes="{}{}{}".format(event.description, " (Override)" if event.user_override == "1" else "", " (Extended)" if event.extended_bolus == "1" else "")
            )

        add_count += 1

        logger.info("  Processing bolus: %s entry: %s" % (event, entry))
        if not pretend:
            nightscout.upload_entry(entry)

    return add_count
