from tconnectsync.domain.therapy_event import BolusTherapyEvent, CGMTherapyEvent, BGTherapyEvent
from tconnectsync.parser.tconnect import TConnectEntry

import logging

logger = logging.getLogger(__name__)

def split_therapy_events(ciqTherapyEvents):
    bolusEvents = []
    cgmEvents = []
    bgEvents = []
    for e in ciqTherapyEvents['event']:
        event = TConnectEntry.parse_therapy_event(e)
        if isinstance(event, BolusTherapyEvent):
            bolusEvents.append(event)
        elif isinstance(event, CGMTherapyEvent): 
            cgmEvents.append(event)
        elif isinstance(event, BGTherapyEvent):
            bgEvents.append(event)
        
    logger.debug("split_therapy_events: %d bolus, %d CGM, %d BG" % (len(bolusEvents), len(cgmEvents), len(bgEvents)))
    # TODO: BG events (CGM Calibration) values are not currently returned from ciq_therapy_events.py
    return bolusEvents, cgmEvents
