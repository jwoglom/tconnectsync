#!/usr/bin/env python3

import sys
import datetime
import json
import hashlib
import requests
import arrow
import argparse
import time

from tconnectsync.api import TConnectApi
from tconnectsync.api.common import ApiException
from tconnectsync.process import process_time_range

try:
    from tconnectsync.secret import (
        TCONNECT_EMAIL,
        TCONNECT_PASSWORD,
        PUMP_SERIAL_NUMBER,
        TIMEZONE_NAME
    )
except Exception:
    print('Unable to import secret.py')
    sys.exit(1)



def parse_args():
    parser = argparse.ArgumentParser(description="Syncs bolus, basal, and IOB data from Tandem Diabetes t:connect to Nightscout.")
    parser.add_argument('--pretend', dest='pretend', action='store_const', const=True, default=False, help='Pretend mode: do not upload any data to Nightscout.')
    parser.add_argument('--start-date', dest='start_date', type=str, default=None, help='The oldest date to process data from. Must be specified with --end-date.')
    parser.add_argument('--end-date', dest='end_date', type=str, default=None, help='The newest date to process data until (inclusive). Must be specified with --start-date.')
    parser.add_argument('--days', dest='days', type=int, default=1, help='The number of days of t:connect data to read in. Cannot be used with --from-date and --until-date.')
    parser.add_argument('--auto-update', dest='auto_update', action='store_const', const=True, default=False, help='If set, continuously checks for updates from t:connect and syncs with Nightscout.')

    return parser.parse_args()

def main():
    args = parse_args()

    if args.pretend:
        print("Pretend mode: will not write to Nightscout")

    if args.auto_update and (args.start_date or args.end_date):
        raise Exception('Auto-update cannot be used with start/end date')

    if args.start_date and args.end_date:
        time_start = arrow.get(args.start_date)
        time_end = arrow.get(args.end_date)
    else:
        time_end = datetime.datetime.now()
        time_start = time_end - datetime.timedelta(days=args.days)

    if time_end < time_start:
        raise Exception('time_start must be before time_end')

    tconnect = TConnectApi(TCONNECT_EMAIL, TCONNECT_PASSWORD)

    if args.auto_update:
        # Read from android api, find exact interval to cut down on API calls
        # Refresh API token. If failure, die, have wrapper script re-run.

        last_event_index = None
        last_event_time = None
        time_diffs = []
        while True:
            last_event = tconnect.android.last_event_uploaded(PUMP_SERIAL_NUMBER)
            if not last_event_index or last_event['maxPumpEventIndex'] > last_event_index:
                now = time.time()
                print('New event index:', last_event['maxPumpEventIndex'], 'last:', last_event_index)

                if args.pretend:
                    print('Would update now')
                else:
                    added = process_time_range(tconnect, time_start, time_end, args.pretend)
                    print('Added', added, 'items')

                if last_event_index:
                    time_diffs.append(now - last_event_time)
                    print('Time diffs:', time_diffs)

                last_event_index = last_event['maxPumpEventIndex']
                last_event_time = now
            else:
                print('No event index change:', last_event['maxPumpEventIndex'])

                if len(time_diffs) > 2:
                    print('Sleeping 60 seconds after unexpected no index change')
                    time.sleep(60)
                    continue

            sleep_secs = 60
            if len(time_diffs) > 10:
                time_diffs = time_diffs[1:]

            if len(time_diffs) > 2:
                sleep_secs = sum(time_diffs) / len(time_diffs)

            # Sleep for a rolling average of time between updates
            print('Sleeping for', sleep_secs, 'sec')
            time.sleep(sleep_secs)
    else:
        print("Processing data between", time_start, "and", time_end)
        added = process_time_range(tconnect, time_start, time_end, args.pretend)
        print("Added", added, "items")

if __name__ == '__main__':
    main()