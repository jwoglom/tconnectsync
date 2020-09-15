#!/usr/bin/env python3

import sys
import datetime
import json
import hashlib
import requests
import arrow

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
        print(i)
        if i["time"] in suspensionEvents:
            i["suspendReason"] = suspensionEvents[i["time"]]["suspendReason"]

    return basalEvents

def ns_write_basal_events(basalEvents):
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
        print("Processing basal:", event, "entry:", entry)
        upload_nightscout(entry)

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

def ns_write_bolus_events(bolusEvents):
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

        print("Processing bolus:", event, "entry:", entry)
        upload_nightscout(entry)

def process_iob_events(iobdata):
    iobEvents = []
    for d in iobdata:
        iobEvents.append(TConnectEntry.parse_iob_entry(d))

    iobEvents.sort(key=lambda x: arrow.get(x["time"]))

    return iobEvents

def ns_write_iob_events(iobEvents):
    last_upload = last_uploaded_nightscout_activity(IOB_ACTIVITYTYPE)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    print("Last Nightscout iob upload:", last_upload_time)

    event = iobEvents[-1]
    if last_upload_time and arrow.get(event["time"]) <= last_upload_time:
        print("Skipping already uploaded iob event:", event)
        return

    entry = NightscoutEntry.iob(
        iob=event["iob"],
        created_at=event["time"]
    )

    print("Processing iob:", event, "entry:", entry)
    upload_nightscout(entry, entity='activity')

    # Delete the previous activity
    if last_upload and '_id' in last_upload:
        print("Deleting old iob entry:", last_upload)
        delete_nightscout('activity/{}'.format(last_upload['_id']))

def main():
    now = datetime.datetime.now()

    tconnect = TConnectApi(TCONNECT_EMAIL, TCONNECT_PASSWORD)

    basaldata = tconnect.therapy_timeline(now - datetime.timedelta(days=1), now)

    # open("basaldata.json","w").write(json.dumps(data))
    # basaldata = json.loads(open("basaldata.json").read())

    basalEvents = process_basal_events(basaldata)
    ns_write_basal_events(basalEvents)

    csvdata = tconnect.therapy_timeline_csv(now - datetime.timedelta(days=1), now)
    cgmdata, iobdata, bolusdata = csvdata

    print("Most recent cgmdata:", cgmdata[-1])

    # open("csvdata.json", "w").write(json.dumps(csvdata))
    # cgmdata, iobdata, bolusdata = json.loads(open("csvdata.json").read())

    bolusEvents = process_bolus_events(bolusdata)
    ns_write_bolus_events(bolusEvents)

    iobEvents = process_iob_events(iobdata)
    ns_write_iob_events(iobEvents)

if __name__ == '__main__':
    main()