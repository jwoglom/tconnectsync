#!/usr/bin/env python3

import sys
import datetime
import json
import hashlib
import requests
import arrow

from api import TConnectApi
from parser import TConnectEntry
from nightscout import NightscoutEntry, upload_nightscout

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

def main():
    now = datetime.datetime.now()

    # tconnect = TConnectApi(TCONNECT_EMAIL, TCONNECT_PASSWORD)
    # data = tconnect.therapy_timeline(now - datetime.timedelta(days=1), now)
    # open("basaldata.json","w").write(json.dumps(data))
    
    data = json.loads(open("basaldata.json").read())
    basalEvents = process_basal_events(data)

    #csvdata = tconnect.therapy_timeline_csv()
    #open("csvdata.json", "w").write(json.dumps(csvdata))
    # csvdata = json.loads(open("csvdata.json").read())

    # for b in csvdata[1]:
    #     print(TConnectEntry.parse_iob_entry(b))








    


if __name__ == '__main__':
    main()