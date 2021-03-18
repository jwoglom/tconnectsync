from datetime import datetime

from .api.common import ApiException
from .sync.basal import (
    process_ciq_basal_events,
    add_csv_basal_events,
    ns_write_basal_events
)
from .sync.bolus import (
    process_bolus_events,
    ns_write_bolus_events
)
from .sync.iob import (
    process_iob_events,
    ns_write_iob_events
)

"""
Given a TConnectApi object and start/end range, performs a single
cycle of synchronizing data within the time range.
If pretend is true, then doesn't actually write data to Nightscout.
"""
def process_time_range(tconnect, time_start, time_end, pretend):
    print("Downloading t:connect ControlIQ data")
    try:
        ciqTherapyTimelineData = tconnect.controliq.therapy_timeline(time_start, time_end)
    except ApiException as e:
        # The ControlIQ API returns a 404 if the user did not have a ControlIQ enabled
        # device in the time range which is queried. Since it launched in early 2020,
        # ignore 404's before February.
        if e.status_code == 404 and time_start.date() < datetime.date(2020, 2, 1):
            print("Ignoring HTTP 404 for ControlIQ API request before Feb 2020")
            ciqTherapyTimelineData = None
        else:
            raise e

    print("Downloading t:connect CSV data")
    csvdata = tconnect.ws2.therapy_timeline_csv(time_start, time_end)

    readingData = csvdata["readingData"]
    iobData = csvdata["iobData"]
    csvBasalData = csvdata["basalData"]
    bolusData = csvdata["bolusData"]

    if readingData and len(readingData) > 0:
        print("Last CGM reading from t:connect:", readingData[-1]['EventDateTime'] if 'EventDateTime' in readingData[-1] else readingData)

    added = 0

    basalEvents = process_ciq_basal_events(ciqTherapyTimelineData)
    if csvBasalData:
        add_csv_basal_events(basalEvents, csvBasalData)

    added += ns_write_basal_events(basalEvents, pretend=pretend)


    bolusEvents = process_bolus_events(bolusData)
    added += ns_write_bolus_events(bolusEvents, pretend=pretend)

    iobEvents = process_iob_events(iobData)
    added += ns_write_iob_events(iobEvents, pretend=pretend)

    return added