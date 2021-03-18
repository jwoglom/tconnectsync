import arrow

from ..parser.nightscout import (
    BOLUS_EVENTTYPE,
    NightscoutEntry
)
from ..nightscout import (
    last_uploaded_nightscout_entry,
    put_nightscout,
    upload_nightscout
)
from ..parser.tconnect import TConnectEntry

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
                parsed["description"] += " (%s)" % parsed["completion"]
            else:
                print("Skipping non-completed bolus data:", b, "parsed:", parsed)
                continue
        bolusEvents.append(parsed)

    bolusEvents.sort(key=lambda event: arrow.get(event["completion_time"] if not event["extended_bolus"] else event["bolex_start_time"]))

    return bolusEvents

"""
Given processed bolus data, adds bolus events to Nightscout.
"""
def ns_write_bolus_events(bolusEvents, pretend=False):
    last_upload = last_uploaded_nightscout_entry(BOLUS_EVENTTYPE)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    print("Last Nightscout bolus upload:", last_upload_time)

    add_count = 0
    for event in bolusEvents:
        if last_upload_time and arrow.get(event["completion_time"]) <= last_upload_time:
            if pretend:
                print("Skipping basal event before last upload time:", event)
            continue

        entry = NightscoutEntry.bolus(
            bolus=event["insulin"],
            carbs=event["carbs"],
            created_at=event["completion_time"] if not event["extended_bolus"] else event["bolex_start_time"],
            notes="{}{}{}".format(event["description"], " (Override)" if event["user_override"] == "1" else "", " (Extended)" if event["extended_bolus"] == "1" else "")
        )

        add_count += 1

        print("  Processing bolus:", event, "entry:", entry)
        if not pretend:
            upload_nightscout(entry)

    return add_count
