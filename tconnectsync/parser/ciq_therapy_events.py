from tconnectsync.domain.therapy_event import BolusTherapyEvent, CGMTherapyEvent
from tconnectsync.parser.tconnect import TConnectEntry


def split_therapy_events(ciqTherapyEvents):
    bolusEvents = []
    cgmEvents = []
    for e in ciqTherapyEvents['event']:
        event = TConnectEntry.parse_therapy_event(e)
        if type(event) == BolusTherapyEvent:
            bolusEvents.append(event)
        elif type(event) == CGMTherapyEvent:
            cgmEvents.append(event)
        
    
    return bolusEvents, cgmEvents
