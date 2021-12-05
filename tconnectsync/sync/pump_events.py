import arrow
import logging

from ..parser.nightscout import (
    NightscoutEntry
)
from ..parser.tconnect import TConnectEntry

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
def ns_write_pump_events(nightscout, iobEvents, pretend=False):
    return 0