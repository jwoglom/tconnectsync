#!/usr/bin/env python3

import sys
import datetime
import json
import hashlib
import requests
import arrow
import argparse

from api import TConnectApi, ApiException
from parser import TConnectEntry
from nightscout import (
    NightscoutEntry,
    upload_nightscout,
    delete_nightscout,
    last_uploaded_nightscout_entry,
    last_uploaded_nightscout_activity,
    BASAL_EVENTTYPE,
    BOLUS_EVENTTYPE,
    IOB_ACTIVITYTYPE
)

try:
    from secret import TCONNECT_EMAIL, TCONNECT_PASSWORD
except Exception:
    print('Unable to import secret.py')
    sys.exit(1)

"""
Merges together input from the therapy timeline API into a digestable format of basal data.
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
Processes basal data input from the therapy timeline CSV (which only exists for pre Control-IQ data) into a digestable format.
"""
def add_csv_basal_events(basalEvents, data):
    last_entry = None
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

    for event in basalEvents:
        if last_upload_time and arrow.get(event["time"]) <= last_upload_time:
            if pretend:
                print("Skipping basal event before last upload time:", event)
            continue

        entry = NightscoutEntry.basal(
            value=event["basal_rate"],
            duration_mins=event["duration_mins"],
            created_at=event["time"],
            reason=event["delivery_type"]
        )
        print("  Processing basal:", event, "entry:", entry)
        if not pretend:
            upload_nightscout(entry)

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

        print("  Processing bolus:", event, "entry:", entry)
        if not pretend:
            upload_nightscout(entry)

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
        return

    event = iobEvents[-1]
    if last_upload_time and arrow.get(event["time"]) <= last_upload_time:
        print("  Skipping already uploaded iob event:", event)
        return

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

def process_time_range(tconnect, time_start, time_end, pretend):
    print("Downloading t:connect ControlIQ data")
    try:
        ciqBasalData = tconnect.therapy_timeline(time_start, time_end)
    except ApiException as e:
        # The ControlIQ API returns a 404 if the user did not have a ControlIQ enabled
        # device in the time range which is queried. Since it launched in early 2020,
        # ignore 404's before February.
        if e.status_code == 404 and time_start.date() < datetime.date(2020, 2, 1):
            print("Ignoring HTTP 404 for ControlIQ API request before Feb 2020")
            ciqBasalData = None
        else:
            raise e

    print("Downloading t:connect CSV data")
    csvdata = tconnect.therapy_timeline_csv(time_start, time_end)

    readingData = csvdata["readingData"]
    iobData = csvdata["iobData"]
    csvBasalData = csvdata["basalData"]
    bolusData = csvdata["bolusData"]

    if readingData and len(readingData) > 0:
        print("Last CGM reading from t:connect:", readingData[-1])

    basalEvents = process_ciq_basal_events(ciqBasalData)
    if csvBasalData:
        add_csv_basal_events(basalEvents, csvBasalData)

    ns_write_basal_events(basalEvents, pretend=pretend)


    bolusEvents = process_bolus_events(bolusData)
    ns_write_bolus_events(bolusEvents, pretend=pretend)

    iobEvents = process_iob_events(iobData)
    ns_write_iob_events(iobEvents, pretend=pretend)

def parse_args():
    parser = argparse.ArgumentParser(description="Syncs bolus, basal, and IOB data from Tandem Diabetes t:connect to Nightscout.")
    parser.add_argument('--pretend', dest='pretend', action='store_const', const=True, default=False, help='Pretend mode: do not upload any data to Nightscout.')
    parser.add_argument('--start-date', dest='start_date', type=str, default=None, help='The oldest date to process data from. Must be specified with --end-date.')
    parser.add_argument('--end-date', dest='end_date', type=str, default=None, help='The newest date to process data until (inclusive). Must be specified with --start-date.')
    parser.add_argument('--days', dest='days', type=int, default=1, help='The number of days of t:connect data to read in. Cannot be used with --from-date and --until-date.')

    return parser.parse_args()

def main():
    args = parse_args()

    if args.pretend:
        print("Pretend mode: will not write to Nightscout")

    if args.start_date and args.end_date:
        time_start = arrow.get(args.start_date)
        time_end = arrow.get(args.end_date)
    else:
        time_end = datetime.datetime.now()
        time_start = time_end - datetime.timedelta(days=args.days)

    if time_end < time_start:
        raise Exception('time_start must be before time_end')

    print("Processing data between", time_start, "and", time_end)

    tconnect = TConnectApi(TCONNECT_EMAIL, TCONNECT_PASSWORD)

    process_time_range(tconnect, time_start, time_end, args.pretend)

if __name__ == '__main__':
    main()