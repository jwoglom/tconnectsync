import arrow
import logging

from ..parser.nightscout import (
    BOLUS_EVENTTYPE,
    NightscoutEntry
)
from ..parser.tconnect import TConnectEntry

logger = logging.getLogger(__name__)

"""
Given bolus data input from the therapy timeline CSV, converts it into a digestable format.
"""
def process_bolus_events(bolusdata):
    bolusEvents = []

    for b in bolusdata:
        parsed = TConnectEntry.parse_bolus_entry(b)
        if parsed["completion"] != "Completed":
            if parsed["insulin"] and float(parsed["insulin"]) > 0:
                # Count non-completed bolus if any insulin was delivered (vs. the amount of insulin requested)
                parsed["description"] += " (%s: requested %s units)" % (parsed["completion"], parsed["requested_insulin"])
            else:
                logger.warning("Skipping non-completed bolus data (was a bolus in progress?): %s parsed: %s" % (b, parsed))
                continue
        bolusEvents.append(parsed)

    bolusEvents.sort(key=lambda event: arrow.get(event["completion_time"] if not event["extended_bolus"] else event["bolex_start_time"]))

    return bolusEvents

"""
Given processed bolus data, adds bolus events to Nightscout.
"""
def ns_write_bolus_events(nightscout, bolusEvents, pretend=False):
    logger.debug("ns_write_bolus_events: querying for last uploaded entry")
    last_upload = nightscout.last_uploaded_entry(BOLUS_EVENTTYPE)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    logger.info("Last Nightscout bolus upload: %s" % last_upload_time)

    add_count = 0
    for event in bolusEvents:
        created_at = event["completion_time"] if not event["extended_bolus"] else event["bolex_start_time"]
        if last_upload_time and arrow.get(created_at) <= last_upload_time:
            if pretend:
                logger.info("Skipping basal event before last upload time: %s" % event)
            continue

        entry = NightscoutEntry.bolus(
            bolus=event["insulin"],
            carbs=event["carbs"],
            created_at=created_at,
            notes="{}{}{}".format(event["description"], " (Override)" if event["user_override"] == "1" else "", " (Extended)" if event["extended_bolus"] == "1" else "")
        )

        add_count += 1

        logger.info("  Processing bolus: %s entry: %s" % (event, entry))
        if not pretend:
            nightscout.upload_entry(entry)

    return add_count
