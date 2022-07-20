import arrow
import logging

from ..parser.nightscout import (
    SITECHANGE_EVENTTYPE,
    BASALSUSPENSION_EVENTTYPE,
    EXERCISE_EVENTTYPE,
    SLEEP_EVENTTYPE,
    ACTIVITY_EVENTTYPE,
    NightscoutEntry
)
from ..parser.tconnect import TConnectEntry
from ..secret import SKIP_NS_LAST_UPLOADED_CHECK

logger = logging.getLogger(__name__)

"""
Given a list of "activity events" from the CIQ therapy timeline endpoint,
process it into our internal events format.

These events contain a duration.
"""
def process_ciq_activity_events(data):
    events = []

    for event in data["events"]:
        events.append(TConnectEntry.parse_ciq_activity_event(event))

    return events

"""
Given a list of "basal suspension events" from the basalsuspension WS2 endpoint,
process it into our internal events format.

These events do NOT contain a duration.
"""
def process_basalsuspension_events(data):
    events = []

    for event in data['BasalSuspension']:
        parsed = TConnectEntry.parse_basalsuspension_event(event)

        if parsed:
            events.append(parsed)
    

    return events

"""
Given processed pump event data (of various types), write them to Nightscout
"""
def ns_write_pump_events(nightscout, pumpEvents, pretend=False, time_start=None, time_end=None):
    count = 0

    siteChangeEvents = []
    emptyCartEvents = []
    userSuspendedEvents = []
    exerciseEvents = []
    sleepEvents = []
    activityEvents = []

    for event in pumpEvents:
        if event["event_type"] == TConnectEntry.BASALSUSPENSION_EVENTS["site-cart"]:
            siteChangeEvents.append(event)
        elif event["event_type"] in TConnectEntry.BASALSUSPENSION_EVENTS["alarm"]:
            emptyCartEvents.append(event)
        elif event["event_type"] in TConnectEntry.BASALSUSPENSION_EVENTS["manual"]:
            userSuspendedEvents.append(event)
        elif event["event_type"] == "Exercise":
            exerciseEvents.append(event)
        elif event["event_type"] == "Sleep":
            sleepEvents.append(event)
        elif event["event_type"] in TConnectEntry.ACTIVITY_EVENTS.values():
            activityEvents.append(event)
            
    logger.debug("siteChangeEvents: %s" % siteChangeEvents)
    logger.debug("emptyCartEvents: %s" % emptyCartEvents)
    logger.debug("userSuspendedEvents: %s" % userSuspendedEvents)
    logger.debug("exerciseEvents: %s" % exerciseEvents)
    logger.debug("sleepEvents: %s" % sleepEvents)
    logger.debug("activityEvents: %s" % activityEvents)
    
    count += ns_write_pump_sitechange_events(nightscout, siteChangeEvents, pretend=pretend, time_start=time_start, time_end=time_end)
    count += ns_write_empty_cart_events(nightscout, emptyCartEvents, pretend=pretend, time_start=time_start, time_end=time_end)
    count += ns_write_user_suspended_events(nightscout, userSuspendedEvents, pretend=pretend, time_start=time_start, time_end=time_end)

    count += ns_write_exercise_activity_events(nightscout, exerciseEvents, pretend=pretend, time_start=time_start, time_end=time_end)
    count += ns_write_sleep_activity_events(nightscout, sleepEvents, pretend=pretend, time_start=time_start, time_end=time_end)
    count += ns_write_activity_events(nightscout, activityEvents, pretend=pretend, time_start=time_start, time_end=time_end)

    return count

def ns_write_pump_sitechange_events(nightscout, siteChangeEvents, pretend=False, time_start=None, time_end=None):
    return _ns_write_pump_events(
        nightscout, 
        siteChangeEvents, 
        lambda event: NightscoutEntry.sitechange(
            created_at=event["time"],
            reason=event["event_type"]
        ),
        SITECHANGE_EVENTTYPE,
        pretend=pretend,
        time_start=time_start,
        time_end=time_end)

def ns_write_empty_cart_events(nightscout, emptyCartEvents, pretend=False, time_start=None, time_end=None):
    return _ns_write_pump_events(
        nightscout, 
        emptyCartEvents, 
        lambda event: NightscoutEntry.basalsuspension(
            created_at=event["time"],
            reason=event["event_type"]
        ),
        BASALSUSPENSION_EVENTTYPE,
        pretend=pretend,
        time_start=time_start,
        time_end=time_end)

def ns_write_user_suspended_events(nightscout, userSuspendedEvents, pretend=False, time_start=None, time_end=None):
    return _ns_write_pump_events(
        nightscout, 
        userSuspendedEvents, 
        lambda event: NightscoutEntry.basalsuspension(
            created_at=event["time"],
            reason=event["event_type"]
        ),
        BASALSUSPENSION_EVENTTYPE,
        pretend=pretend,
        time_start=time_start,
        time_end=time_end)

def ns_write_exercise_activity_events(nightscout, exerciseEvents, pretend=False, time_start=None, time_end=None):
    return _ns_write_pump_events(
        nightscout, 
        exerciseEvents, 
        lambda event: NightscoutEntry.activity(
            created_at=event["time"],
            reason=event["event_type"],
            duration=event["duration_mins"],
            event_type=EXERCISE_EVENTTYPE
        ),
        EXERCISE_EVENTTYPE,
        pretend=pretend,
        time_start=time_start,
        time_end=time_end)

def ns_write_sleep_activity_events(nightscout, sleepEvents, pretend=False, time_start=None, time_end=None):
    return _ns_write_pump_events(
        nightscout, 
        sleepEvents, 
        lambda event: NightscoutEntry.activity(
            created_at=event["time"],
            reason=event["event_type"],
            duration=event["duration_mins"],
            event_type=SLEEP_EVENTTYPE
        ),
        SLEEP_EVENTTYPE,
        pretend=pretend,
        time_start=time_start,
        time_end=time_end)

def ns_write_activity_events(nightscout, activityEvents, pretend=False, time_start=None, time_end=None):
    return _ns_write_pump_events(
        nightscout, 
        activityEvents, 
        lambda event: NightscoutEntry.activity(
            created_at=event["time"],
            reason=event["event_type"],
            duration=event["duration_mins"]
        ),
        ACTIVITY_EVENTTYPE,
        pretend=pretend,
        time_start=time_start,
        time_end=time_end)

def _ns_write_pump_events(nightscout, events, buildNsEventFunc, eventType, pretend=False, time_start=None, time_end=None):
    if len(events) == 0:
        logger.debug("No %s events to process" % eventType)
        return 0

    logger.debug("ns_write_pump_events: querying for last %s" % eventType)
    last_upload = nightscout.last_uploaded_entry(eventType, time_start=time_start, time_end=time_end)
    last_upload_time = None
    if last_upload:
        last_upload_time = arrow.get(last_upload["created_at"])
    logger.info("Last Nightscout %s: %s" % (eventType, last_upload_time))

    if SKIP_NS_LAST_UPLOADED_CHECK:
        logger.warning("Overriding last upload check")
        last_upload = None
        last_upload_time = None

    add_count = 0
    for event in events:
        created_at = event["time"]
        if last_upload_time and arrow.get(created_at) <= last_upload_time:
            skip = True
            if "duration_mins" in event.keys() and "duration" in last_upload.keys():
                if created_at == last_upload["created_at"] and float(event["duration_mins"]) > float(last_upload["duration"]):
                    logger.info("Latest %s event needs updating: duration has increased from %s to %s: %s" % (eventType, last_upload["duration"], event["duration_mins"], event))
                    logger.info("Deleting previous %s: %s" % (eventType, last_upload))
                    nightscout.delete_entry('treatments/%s' % last_upload["_id"])
                    skip = False
            
            if skip:
                if pretend:
                    logger.info("Skipping %s pump event before last upload time: %s (time range: %s - %s)" % (eventType, event, time_start, time_end))
                continue

        entry = buildNsEventFunc(event)

        add_count += 1

        logger.info("  Processing %s: %s entry: %s" % (eventType, event, entry))
        if not pretend:
            nightscout.upload_entry(entry)

    return add_count
