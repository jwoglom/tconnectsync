#!/usr/bin/env python3

import sys
import datetime
import json
import hashlib
import requests
import arrow
import argparse

from api import TConnectApi
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
def process_basal_events(data):
    suspensionEvents = {}
    for s in data["suspensionDeliveryEvents"]:
        entry = TConnectEntry.parse_suspension_entry(s)
        suspensionEvents[entry["time"]] = entry

    basalEvents = []
    for b in data["basal"]["tempDeliveryEvents"]:
        basalEvents.append(TConnectEntry.parse_basal_entry(b, delivery_type="tempDelivery"))

    for b in data["basal"]["algorithmDeliveryEvents"]:
        basalEvents.append(TConnectEntry.parse_basal_entry(b, delivery_type="algorithmDelivery"))

    for b in data["basal"]["profileDeliveryEvents"]:
        basalEvents.append(TConnectEntry.parse_basal_entry(b, delivery_type="profileDelivery"))

    basalEvents.sort(key=lambda x: arrow.get(x["time"]))

    for i in basalEvents:
        if i["time"] in suspensionEvents:
            i["suspendReason"] = suspensionEvents[i["time"]]["suspendReason"]

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
            #print("Skipping already uploaded basal event:", event)
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
            print("Skipping non-completed bolus data:", b, "parsed:", parsed)
            continue
        bolusEvents.append(parsed)

    bolusEvents.sort(key=lambda x: arrow.get(x["completion_time"]))

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
            #print("Skipping already uploaded bolus event:", event)
            continue

        entry = NightscoutEntry.bolus(
            bolus=event["insulin"],
            carbs=event["carbs"],
            created_at=event["completion_time"],
            notes="{}{}".format(event["description"], " (Override)" if event["user_override"] == "1" else "")
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


def parse_args():
    parser = argparse.ArgumentParser(description="Syncs bolus, basal, and IOB data from Tandem Diabetes t:connect to Nightscout.")
    parser.add_argument('--pretend', dest='pretend', action='store_const', const=True, default=False, help='Pretend mode: do not upload any data to Nightscout.')
    parser.add_argument('--days', dest='days', type=int, default=1, help='The number of days of t:connect data to read in')

    return parser.parse_args()

def main():
    args = parse_args()

    if args.pretend:
        print("Pretend mode: will not write to Nightscout")

    time_end = datetime.datetime.now()
    time_start = time_end - datetime.timedelta(days=args.days)

    tconnect = TConnectApi(TCONNECT_EMAIL, TCONNECT_PASSWORD)

    print("Reading basal data from t:connect")
    basaldata = tconnect.therapy_timeline(time_start, time_end)

    print("Reading bolus and IOB data from t:connect")
    cgmdata, iobdata, bolusdata = tconnect.therapy_timeline_csv(time_start, time_end)

    if cgmdata and len(cgmdata) > 0:
        print("Last CGM reading from t:connect:", cgmdata[-1])

    basalEvents = process_basal_events(basaldata)
    ns_write_basal_events(basalEvents, pretend=args.pretend)

    bolusEvents = process_bolus_events(bolusdata)
    ns_write_bolus_events(bolusEvents, pretend=args.pretend)

    iobEvents = process_iob_events(iobdata)
    ns_write_iob_events(iobEvents, pretend=args.pretend)

if __name__ == '__main__':
    main()