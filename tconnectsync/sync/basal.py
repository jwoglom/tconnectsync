import arrow

from ..parser.nightscout import (
    BASAL_EVENTTYPE,
    NightscoutEntry
)
from ..nightscout import (
    last_uploaded_nightscout_entry,
    put_nightscout,
    upload_nightscout
)
from ..parser.tconnect import TConnectEntry


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
def ns_write_basal_events(basalEvents, pretend=False):
    last_upload = last_uploaded_nightscout_entry(BASAL_EVENTTYPE)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    print("Last Nightscout basal upload:", last_upload_time)

    add_count = 0
    for event in basalEvents:
        if last_upload_time and arrow.get(event["time"]) < last_upload_time:
            if pretend:
                print("Skipping basal event before last upload time:", event)
            continue

        recent_needs_update = False
        if last_upload_time and arrow.get(event["time"]) == last_upload_time:
            # If this entry has the same time as the most recent upload, but
            # has newer info, then delete and recreate it.
            recent_needs_update = (round(last_upload["duration"]) < round(event["duration_mins"]))

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

        print("  Processing basal:", event, "entry:", entry)
        if recent_needs_update:
            print("Replacing last uploaded entry:", last_upload)
            if not pretend:
                entry['_id'] = last_upload['_id']
                put_nightscout(entry, entity='treatments')
        elif not pretend:
            upload_nightscout(entry)

    return add_count
