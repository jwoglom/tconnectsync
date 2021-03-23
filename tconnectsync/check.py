from .nightscout import api_status

from .secret import PUMP_SERIAL_NUMBER


"""
Attempts to authenticate with each t:connect API,
and returns the output of a sample API call from each.
Also attempts to connect to the Nightscout API.
"""
def check_login(tconnect, time_start, time_end):
    errors = 0

    print("Logging in to t:connect ControlIQ API...")
    try:
        summary = tconnect.controliq.dashboard_summary(time_start, time_end)
        print("ControlIQ dashboard summary: %s" % summary)
    except Exception as e:
        print("Error occurred querying ControlIQ API: %s" % e)
        errors += 1

    print("\nLogging in to t:connect WS2 API...")
    try:
        summary = tconnect.ws2.basaliqtech(time_start, time_end)
        print("WS2 basaliq status: %s" % summary)
    except Exception as e:
        print("Error occurred querying WS2 API: %s" % e)
        errors += 1

    print("\nLogging in to t:connect Android API...")
    try:
        summary = tconnect.android.user_profile()
        print("Android user profile: %s" % summary)

        event = tconnect.android.last_event_uploaded(PUMP_SERIAL_NUMBER)
        print("\nAndroid last uploaded event: %s" % event)
    except Exception as e:
        print("Error occurred querying Android API: %s" % e)
        errors += 1

    print("\nLogging in to Nightscout...")
    try:
        status = api_status()
        print("\nNightscout status: %s" % status)
    except Exception as e:
        print("Error occurred querying Nightscout API: %s" % e)
        errors += 1

    if errors == 0:
        print("\nNo API errors returned!")
    else:
        print("\nAPI errors occurred. Please check the errors above.")

