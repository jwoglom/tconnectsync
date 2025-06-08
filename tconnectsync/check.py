import sys
import time
import arrow
import logging
import traceback
import pkg_resources
import collections
from datetime import datetime
from pprint import pformat as pformat_base

from .nightscout import NightscoutApi
from .parser.nightscout import BASAL_EVENTTYPE, BOLUS_EVENTTYPE
from .parser.tconnect import TConnectEntry
from .domain.tandemsource.event_class import EventClass
from .sync.tandemsource.choose_device import ChooseDevice

try:
    __version__ = pkg_resources.require("tconnectsync")[0].version
except Exception:
    __version__ = "UNKNOWN"

"""
Attempts to authenticate with each t:connect API,
and returns the output of a sample API call from each.
Also attempts to connect to the Nightscout API.
"""
def check_login(tconnect, time_start, time_end, verbose=False, sanitize=True):
    errors = 0

    loglines = []
    def log(*args):
        print(*args)
        loglines.append(" ".join([str(i) for i in args]) + "\n")

    def log_err(e):
        try:
            out = ''.join(list(traceback.TracebackException.from_exception(e).format()))
            log(out)
        except Exception:
            log("could not log exception traceback: {}".format(e))

    def debug(*args):
        if verbose:
            print(*args)
        loglines.append(" ".join([str(i) for i in args]) + "\n")

    log("tconnectsync version %s" % __version__)
    log("Python version %s" % sys.version)
    log("System platform %s" % sys.platform)
    log("Running checks with time range %s to %s" % (time_start, time_end))
    log("Current time: %s" % datetime.now())
    log("time.tzname: %s" % str(time.tzname))

    log("Loading secrets...")
    try:
        from .secret import TCONNECT_EMAIL, TCONNECT_PASSWORD, TCONNECT_REGION, PUMP_SERIAL_NUMBER, NS_URL, NS_SECRET, TIMEZONE_NAME
        from . import secret
    except ImportError as e:
        log("Error: Unable to load config file. Please check your .env file or environment variables")
        log_err(e)

    log(f"Using {TCONNECT_REGION=}")

    if not TCONNECT_EMAIL or TCONNECT_EMAIL == 'email@email.com':
        log("Error: You have not specified a TCONNECT_EMAIL")
        errors += 1

    if not TCONNECT_PASSWORD or TCONNECT_PASSWORD == 'password':
        log("Error: You have not specified a TCONNECT_PASSWORD")
        errors += 1

    if not PUMP_SERIAL_NUMBER or PUMP_SERIAL_NUMBER == '11111111':
        log("Warning: You have not specified a PUMP_SERIAL_NUMBER, so the pump with most recent activity will be automatically used.")

    if not NS_URL or NS_URL == 'https://yournightscouturl/':
        log("Error: You have not specified a NS_URL")
        errors += 1

    if not NS_SECRET or NS_SECRET == 'apisecret':
        log("Error: You have not specified a NS_SECRET")
        errors += 1

    log("TIMEZONE_NAME: %s" % TIMEZONE_NAME)

    log("-----")

    serialNumberToPump = None
    try:
        log("Fetching pump metadata...")
        pumpEventMetadata = tconnect.tandemsource.pump_event_metadata()

        serialNumberToPump = {p['serialNumber']: p for p in pumpEventMetadata}
        log(f'Found {len(serialNumberToPump)} pumps: {serialNumberToPump.keys()}')
        for pumpSerial, pumpDetails in serialNumberToPump.items():
            log(f'Pump {pumpSerial=}: {pumpDetails=}')

        log("Running ChooseDevice...")
        tconnectDevice = ChooseDevice(secret, tconnect).choose()

        log(f'ChooseDevice selected: {tconnectDevice}')

        tconnectDeviceId = tconnectDevice['tconnectDeviceId']

        log(f'Fetching pump events for {tconnectDeviceId=} {time_start=} {time_end=} fetch_all_event_types=False')

        events = tconnect.tandemsource.pump_events(tconnectDeviceId, time_start, time_end, fetch_all_event_types=False)
        events = list(events)

        log(f"Found raw events count: {len(events)}")


        events_first_time = None
        events_last_time = None
        last_event_seqnum = None
        for_eventclass = collections.defaultdict(list)
        for event in events:
            if not events_first_time:
                events_first_time = event.eventTimestamp
            if not events_last_time:
                events_last_time = event.eventTimestamp
            if not last_event_seqnum:
                last_event_seqnum = event.seqNum
            events_first_time = min(events_first_time, event.eventTimestamp)
            events_last_time = max(events_last_time, event.eventTimestamp)
            last_event_seqnum = max(event.seqNum, last_event_seqnum)

            clazz = EventClass.for_event(event)
            if clazz:
                for_eventclass[clazz.name].append(event)

        count_by_eventclass = {k: len(v) for k,v in for_eventclass.items()}
        log(f"Found events count: {count_by_eventclass}")

        log(f"Found first event time: {events_first_time}")
        log(f"Found last event time: {events_last_time}")
        log(f"Found last event sequence number: {last_event_seqnum}")
    except Exception as e:
        log("Error occurred querying Tandem Source:")
        log_err(e)
        errors += 1


    log("-----")

    log("Logging in to Nightscout...")
    try:
        nightscout = NightscoutApi(NS_URL, NS_SECRET)
        status = nightscout.api_status()
        debug("Nightscout status: \n%s" % pformat(status))

        last_upload_basal = nightscout.last_uploaded_entry(BASAL_EVENTTYPE)
        debug("Nightscout last uploaded basal: \n%s" % pformat(last_upload_basal))

        last_upload_bolus = nightscout.last_uploaded_entry(BOLUS_EVENTTYPE)
        debug("Nightscout last uploaded bolus: \n%s" % pformat(last_upload_bolus))
    except Exception as e:
        log("Error occurred querying Nightscout API:")
        log_err(e)
        errors += 1

    log("-----")

    def time_ago(t):
        return '%s ago' % (arrow.now() - arrow.get(t)) if t else 'n/a'



    if errors == 0:
        log("No API errors returned!")
    else:
        log("API errors occurred. Please check the errors above.")


    with open('tconnectsync-check-output.log', 'w') as f:

        if sanitize:
            sanitizedData = {
                'TCONNECT_EMAIL': TCONNECT_EMAIL,
                'TCONNECT_PASSWORD': TCONNECT_PASSWORD,
                'PUMP_SERIAL_NUMBER': PUMP_SERIAL_NUMBER,
                'NS_URL': NS_URL,
                'NS_SECRET': NS_SECRET
            }
            if serialNumberToPump:
                for i, (pumpSerial, pumpDetails) in enumerate(serialNumberToPump.items()):
                    sanitizedData[f'PUMP_SERIAL_{i}'] = pumpSerial
                    sanitizedData[f'TCONNECT_DEVICE_ID_{i}'] = pumpDetails['tconnectDeviceId']
            loglines = [run_sanitize(i, sanitizedData) for i in loglines]

        f.writelines(loglines)

    print("Created file tconnectsync-check-output.log containing additional debugging information.")
    print("For support, you can upload this file to https://github.com/jwoglom/tconnectsync/issues/new")
    if sanitize:
        print("The file -- but NOT the output printed above -- has been sanitized to remove sensitive data.")
    print("Please verify and remove any sensitive data, such as your Nightscout URL/secret and pump serial number,")
    print("as necessary.")

def run_sanitize(s, sanitizedData):
    ret = str(s)
    for k, v in sanitizedData.items():
        if v and len(str(v)) > 0:
            ret = ret.replace(str(v), '[%s]' % k)
    return ret

def pformat(*args, **kwargs):
    kwargs['width'] = 160
    return pformat_base(*args, **kwargs)