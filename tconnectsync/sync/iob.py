import arrow
import logging

from ..parser.nightscout import (
    IOB_ACTIVITYTYPE,
    NightscoutEntry
)
from ..parser.tconnect import TConnectEntry

logger = logging.getLogger(__name__)

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
def ns_write_iob_events(nightscout, iobEvents, pretend=False, time_start=None, time_end=None):
    logger.debug("ns_write_iob_events: querying for last uploaded entry")
    last_upload = nightscout.last_uploaded_activity(IOB_ACTIVITYTYPE, time_start=time_start, time_end=time_end)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    logger.info("Last Nightscout iob upload: %s" % last_upload_time)

    if not iobEvents or len(iobEvents) == 0:
        logger.info("No IOB events present from API: skipping")
        return 0

    event = iobEvents[-1]
    if last_upload_time and arrow.get(event["time"]) <= last_upload_time:
        logger.info("  Skipping already uploaded iob event: %s" % event)
        return 0

    entry = NightscoutEntry.iob(
        iob=event["iob"],
        created_at=event["time"]
    )

    logger.info("  Processing iob: %s entry: %s" % (event, entry))
    if not pretend:
        nightscout.upload_entry(entry, entity='activity')

    # Delete the previous activity
    if last_upload and '_id' in last_upload:
        logger.info("  Deleting old iob entry: %s" % last_upload)
        if not pretend:
            nightscout.delete_entry('activity/{}'.format(last_upload['_id']))

    return 1