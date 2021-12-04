import arrow
import logging

from ..parser.nightscout import (
    NightscoutEntry
)
from ..parser.tconnect import TConnectEntry

logger = logging.getLogger(__name__)

"""
Given a list of "activity events" from the CIQ therapy timeline endpoint,
process it into our internal events format
"""
def process_ciq_activity_events(data):
    events = []

    for event in data["events"]:
        events.push(TConnectEntry.parse_ciq_activity_event(event))

    return events

"""
Given processed pump event data (of various types), write them to Nightscout
"""
def ns_write_pump_events(nightscout, iobEvents, pretend=False):
    pass