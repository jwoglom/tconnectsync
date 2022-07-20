import arrow
import logging

from ..parser.nightscout import (
    BASAL_EVENTTYPE,
    NightscoutEntry
)
from ..parser.tconnect import TConnectEntry
from ..secret import SKIP_NS_LAST_UPLOADED_CHECK

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


    # Suspensions with suspendReason 'control-iq' will match a basal event found above.
    for i in basalEvents:
        if i["time"] in suspensionEvents:
            i["delivery_type"] += " (" + suspensionEvents[i["time"]]["suspendReason"] + " suspension)"

            del suspensionEvents[i["time"]]
    
    # Suspensions with suspendReason 'manual' do not have an associated basal event,
    # and require extra processing.

    basalEvents.sort(key=lambda x: arrow.get(x["time"]))

    unprocessedSuspensions = list(suspensionEvents.values())
    unprocessedSuspensions.sort(key=lambda x: arrow.get(x["time"]))

    # For the remaining suspensions which did not match with an existing basal event,
    # add a new event manually. This means we need to calculate the duration of the
    # suspension.
    newEvents = []
    for i in range(len(basalEvents)):
        if len(unprocessedSuspensions) == 0:
            break

        existingTime = arrow.get(basalEvents[i]["time"])
        unprocessedTime = arrow.get(unprocessedSuspensions[0]["time"])
        
        # If we've found an event which occurs after the suspension, then the
        # difference in their timestamps is the duration of the suspension.
        if i > 0 and existingTime > unprocessedTime:
            suspension = unprocessedSuspensions.pop(0)

            # TConnect's internal duration object tracks the duration in seconds
            seconds = (existingTime - unprocessedTime).seconds

            newEvent = TConnectEntry.manual_suspension_to_basal_entry(suspension, seconds)
            logger.debug("Adding basal event for unprocessed suspension: %s" % newEvent)
            newEvents.append(newEvent)

    # Any remaining suspensions which have not been processed have not ended,
    # which means we do not know their duration; so we will skip them (for now)

    # Add any new events and re-sort
    if newEvents:
        basalEvents += newEvents
        basalEvents.sort(key=lambda x: arrow.get(x["time"]))


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
def ns_write_basal_events(nightscout, basalEvents, pretend=False, time_start=None, time_end=None):
    logger.debug("ns_write_basal_events: querying for last uploaded entry")
    last_upload = nightscout.last_uploaded_entry(BASAL_EVENTTYPE, time_start=time_start, time_end=time_end)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    logger.info("Last Nightscout basal upload: %s" % last_upload_time)

    if SKIP_NS_LAST_UPLOADED_CHECK:
        logger.warning("Overriding last upload check")
        last_upload = None
        last_upload_time = None

    add_count = 0
    for event in basalEvents:
        if last_upload_time and arrow.get(event["time"]) < last_upload_time:
            if pretend:
                logger.info("Skipping basal event before last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
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
