import json
import arrow
import logging

from ..parser.tconnect import TConnectEntry
from ..parser.nightscout import NightscoutEntry

logger = logging.getLogger(__name__)

def process_cgm_events(readingData):
    data = []
    for r in readingData:
        data.append(TConnectEntry.parse_reading_entry(r))
    
    return data

"""
Given reading data and a time, finds the BG reading event which would have
been the current one at that time. e.g., it looks before the given time,
not after.
This is a heuristic for checking whether the BG component of a bolus was
manually entered or inferred based on the pump's CGM.
"""
def find_event_at(cgmEvents, find_time):
    find_t = arrow.get(find_time)
    events = list(map(lambda x: (arrow.get(x["time"]), x), cgmEvents))
    events.sort()

    closestReading = None
    for t, r in events:
        if t > find_t:
            break
        closestReading = r
        
    
    return closestReading
    

"""
Given processed CGM data, adds reading entries to Nightscout.
"""
def ns_write_cgm_events(nightscout, cgmEvents, pretend=False, time_start=None, time_end=None):
    logger.debug("ns_write_cgm_events: querying for last uploaded entry")
    last_upload = nightscout.last_uploaded_bg_entry(time_start=time_start, time_end=time_end)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["dateString"])
    logger.info("Last Nightscout CGM upload: %s" % last_upload_time)

    add_count = 0
    for event in cgmEvents:
        created_at = event["time"]
        if last_upload_time and arrow.get(created_at) <= last_upload_time:
            if pretend:
                logger.info("Skipping CGM event before last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
            continue

        entry = NightscoutEntry.entry(
            sgv=event["bg"],
            created_at=created_at
        )

        add_count += 1

        logger.info("  Processing cgm reading: %s entry: %s" % (event, entry))
        if not pretend:
            nightscout.upload_entry(entry, entity='entries')

    return add_count
