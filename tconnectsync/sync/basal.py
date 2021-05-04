import arrow
import logging

from ..parser.nightscout import (
    BASAL_EVENTTYPE,
    NightscoutEntry
)
from ..parser.tconnect import TConnectEntry

logger = logging.getLogger(__name__)

"""
Merges together input from the therapy timeline API
into a digestable format of basal data.
"""
def process_ciq_basal_events(data):
    if data is None:
        return []

    suspensionEvents = {}
    for s in data["suspensionDeliveryEvents"]:
        entry = TConnectEntry.parse_suspension_entry(s)
        suspensionEvents[entry["time"]] = entry

    basalEvents = []
    for b in data["basal"]["tempDeliveryEvents"]:
        basalEvents.append(TConnectEntry.parse_ciq_basal_entry(b, delivery_type="tempDelivery"))

    for b in data["basal"]["algorithmDeliveryEvents"]:
        basalEvents.append(TConnectEntry.parse_ciq_basal_entry(b, delivery_type="algorithmDelivery"))

    for b in data["basal"]["profileDeliveryEvents"]:
        basalEvents.append(TConnectEntry.parse_ciq_basal_entry(b, delivery_type="profileDelivery"))

    basalEvents.sort(key=lambda x: arrow.get(x["time"]))

    for i in basalEvents:
        if i["time"] in suspensionEvents:
            i["suspendReason"] = suspensionEvents[i["time"]]["suspendReason"]

    return basalEvents

"""
Processes basal data input from the therapy timeline CSV (which only
exists for pre Control-IQ data) into a digestable format.
"""
def add_csv_basal_events(basalEvents, data):
    last_entry = {}
    for row in data:
        entry = TConnectEntry.parse_csv_basal_entry(row)
        if last_entry:
            diff_mins = (arrow.get(entry["time"]) - arrow.get(last_entry["time"])).seconds // 60
            entry["duration_mins"] = diff_mins

        basalEvents.append(entry)
        last_entry = entry

    basalEvents.sort(key=lambda x: arrow.get(x["time"]))
    return basalEvents

"""
Given processed basal data, adds basal events to Nightscout.
"""
def ns_write_basal_events(nightscout, basalEvents, pretend=False):
    logger.debug("ns_write_basal_events: querying for last uploaded entry")
    last_upload = nightscout.last_uploaded_entry(BASAL_EVENTTYPE)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    logger.info("Last Nightscout basal upload: %s" % last_upload_time)

    add_count = 0
    for event in basalEvents:
        if last_upload_time and arrow.get(event["time"]) < last_upload_time:
            if pretend:
                logger.info("Skipping basal event before last upload time: %s" % event)
            continue

        recent_needs_update = False
        if last_upload_time and arrow.get(event["time"]) == last_upload_time:
            # If this entry has the same time as the most recent upload, but
            # has newer info, then delete and recreate it.
            recent_needs_update = (round(last_upload["duration"]) < round(event["duration_mins"]))

            # If the timestamps are identical, and the duration is identical, 
            # then don't upload a duplicate entry of what we already have.
            if not recent_needs_update:
                continue

        reason = event["delivery_type"]
        if "suspendReason" in reason:
            reason += " (" + reason["suspendReason"] + ")"

        entry = NightscoutEntry.basal(
            value=event["basal_rate"],
            duration_mins=event["duration_mins"],
            created_at=event["time"],
            reason=reason
        )

        add_count += 1

        logger.info("  Processing basal: %s entry: %s" % (event, entry))
        if recent_needs_update:
            logger.info("Replacing last uploaded entry: %s" % last_upload)
            if not pretend:
                entry['_id'] = last_upload['_id']
                nightscout.put_entry(entry, entity='treatments')
        elif not pretend:
            nightscout.upload_entry(entry)

    logger.debug("ns_write_basal_events: added %d events" % add_count)
    return add_count
