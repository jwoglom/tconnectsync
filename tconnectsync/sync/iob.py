import arrow

from ..nightscout import (
    IOB_ACTIVITYTYPE,
    NightscoutEntry,
    last_uploaded_nightscout_activity,
    delete_nightscout,
    upload_nightscout
)
from ..parser import TConnectEntry

"""
Given IOB data input from the therapy timeline CSV, converts it into a digestable format.
"""
def process_iob_events(iobdata):
    iobEvents = []
    for d in iobdata:
        iobEvents.append(TConnectEntry.parse_iob_entry(d))

    iobEvents.sort(key=lambda x: arrow.get(x["time"]))

    return iobEvents

"""
Given processed IOB data, creates a single Nightscout activity definition to store IOB.
"""
def ns_write_iob_events(iobEvents, pretend=False):
    last_upload = last_uploaded_nightscout_activity(IOB_ACTIVITYTYPE)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    print("Last Nightscout iob upload:", last_upload_time)

    if not iobEvents or len(iobEvents) == 0:
        print("No IOB events: skipping")
        return 0

    event = iobEvents[-1]
    if last_upload_time and arrow.get(event["time"]) <= last_upload_time:
        print("  Skipping already uploaded iob event:", event)
        return 0

    entry = NightscoutEntry.iob(
        iob=event["iob"],
        created_at=event["time"]
    )

    print("  Processing iob:", event, "entry:", entry)
    if not pretend:
        upload_nightscout(entry, entity='activity')

    # Delete the previous activity
    if last_upload and '_id' in last_upload:
        print("  Deleting old iob entry:", last_upload)
        if not pretend:
            delete_nightscout('activity/{}'.format(last_upload['_id']))

    return 1