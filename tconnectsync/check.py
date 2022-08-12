import sys
import time
import arrow
import logging
import pkg_resources
from datetime import datetime
from pprint import pformat

from .nightscout import NightscoutApi
from .parser.nightscout import BASAL_EVENTTYPE, BOLUS_EVENTTYPE
from .parser.tconnect import TConnectEntry
from .sync.basal import process_ciq_basal_events

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
        from .secret import TCONNECT_EMAIL, TCONNECT_PASSWORD, PUMP_SERIAL_NUMBER, NS_URL, NS_SECRET, TIMEZONE_NAME
    except ImportError as e:
        log("Error: Unable to load config file. Please check your .env file or environment variables")
        log(e)
    
    if not TCONNECT_EMAIL or TCONNECT_EMAIL == 'email@email.com':
        log("Error: You have not specified a TCONNECT_EMAIL")
        errors += 1
    
    if not TCONNECT_PASSWORD or TCONNECT_PASSWORD == 'password':
        log("Error: You have not specified a TCONNECT_PASSWORD")
        errors += 1
    
    if not PUMP_SERIAL_NUMBER or PUMP_SERIAL_NUMBER == '11111111':
        log("Error: You have not specified a PUMP_SERIAL_NUMBER")
        errors += 1
    
    if not NS_URL or NS_URL == 'https://yournightscouturl/':
        log("Error: You have not specified a NS_URL")
        errors += 1
    
    if not NS_SECRET or NS_SECRET == 'apisecret':
        log("Error: You have not specified a NS_SECRET")
        errors += 1

    log("TIMEZONE_NAME: %s" % TIMEZONE_NAME)

    log("-----")

    log("Logging in to t:connect ControlIQ API...")
    try:
        summary = tconnect.controliq.dashboard_summary(time_start, time_end)
        debug("ControlIQ dashboard summary: \n%s" % pformat(summary))
        log("tconnect_software_ver: %s" % tconnect.controliq.tconnect_software_ver)
    except Exception as e:
        log("Error occurred querying ControlIQ API for dashboard_summary:")
        log(e)
        errors += 1
    
    log("Querying ControlIQ therapy_timeline...")
    lastBasalTime = None
    lastBasalDuration = None
    try:
        tt = tconnect.controliq.therapy_timeline(time_start, time_end)
        debug("ControlIQ therapy_timeline: \n%s" % pformat(tt))
        if tt:
            processed_tt = process_ciq_basal_events(tt)
            debug("ControlIQ processed therapy_timeline: \n%s" % pformat(processed_tt))
            if processed_tt:
                log("Last ControlIQ processed therapy_timeline event: \n%s" % pformat(processed_tt[-1]))
                lastBasalTime = processed_tt[-1]['time']
                lastBasalDuration = processed_tt[-1]['duration_mins']
    except Exception as e:
        log("Error occurred querying ControlIQ therapy_timeline:")
        log(e)
        errors += 1
    
    log("Querying ControlIQ therapy_events...")
    try:
        androidevents = tconnect.controliq.therapy_events(time_start, time_end)
        debug("controliq therapy_events: \n%s" % pformat(androidevents))
    except Exception as e:
        log("Error occurred querying ControlIQ therapy_events:")
        log(e)
        errors += 1
    
    log("-----")

    log("Initializing t:connect WS2 API...")
    ws2_loggedin = False
    try:
        summary = tconnect.ws2.basaliqtech(time_start, time_end)
        debug("WS2 basaliq status: \n%s" % pformat(summary))
        ws2_loggedin = True
    except Exception as e:
        log("Error occurred querying WS2 API. This is okay so long as you are not using the PUMP_EVENTS or IOB sync features.")
        log(e)
        errors += 1
    
    lastReadingTime = None
    if ws2_loggedin:
        log("Querying WS2 therapy_timeline_csv...")
        try:
            ttcsv = tconnect.ws2.therapy_timeline_csv(time_start, time_end)
            debug("therapy_timeline_csv: \n%s" % pformat(ttcsv))
            if ttcsv and "readingData" in ttcsv and len(ttcsv["readingData"]) > 0:
                log("Last therapy_timeline_csv reading: \n%s" % pformat(ttcsv["readingData"][-1]))
                lastReadingTime = TConnectEntry._datetime_parse(ttcsv["readingData"][-1]['EventDateTime'])
        except Exception as e:
            log("Error occurred querying WS2 therapy_timeline_csv. This is okay so long as you are not using the PUMP_EVENTS or IOB sync features.")
            log(e)
            errors += 1
    else:
        log("Not able to log in to WS2 API, so skipping therapy_timeline_csv")
    
    log("-----")

    log("Logging in to t:connect Android API...")
    summary = None
    try:
        summary = tconnect.android.user_profile()
        debug("Android user profile: \n%s" % pformat(summary))

        event = tconnect.android.last_event_uploaded(PUMP_SERIAL_NUMBER)
        debug("Android last uploaded event: \n%s" % pformat(event))
    except Exception as e:
        log("Error occurred querying Android API:")
        log(e)
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
        log(e)
        errors += 1

    log("-----")

    def time_ago(t):
        return '%s ago' % (arrow.now() - arrow.get(t)) if t else 'n/a'

    log("Last basal start time: %s (%s)" % (lastBasalTime, time_ago(lastBasalTime)))
    log("Last basal duration: %s" % lastBasalDuration)
    log("Last reading time: %s (%s)" % (lastReadingTime, time_ago(lastReadingTime)))

    log("-----")

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

            if summary:
                sanitizedData.update({
                    'ANDROID_PROFILE_USERID': summary.get('userID'),
                    'ANDROID_PROFILE_PATIENT_FULLNAME': summary.get('patientFullName'),
                    'ANDROID_PROFILE_CAREGIVER_FULLNAME': summary.get('caregiverFullName')
                })

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