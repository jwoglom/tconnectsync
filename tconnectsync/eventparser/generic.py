import struct
import base64
import logging

from dataclasses import dataclass

from .raw_event import RawEvent, EVENT_LEN
from .events import EVENT_IDS
from .json_events import JSON_EVENT_IDS
from .utils import batched

logger = logging.getLogger(__name__)

def Event(x):
    # Accepts either a 26-byte binary event or a pump-logs JSON event (dict).
    if isinstance(x, dict):
        raw_event = RawEvent.build_from_json(x)
        if raw_event.id in JSON_EVENT_IDS:
            return JSON_EVENT_IDS[raw_event.id].build_from_json(x)

        if not raw_event.id in EVENT_IDS:
            # Log unknown events with their property keys for reverse-engineering
            props = ' '.join(x['eventProperties'].keys())
            logger.debug(f"UNKNOWN_JSON_EVENT | id={raw_event.id} | seqNum={raw_event.seqNum} | timestamp={raw_event.timestamp.isoformat()} | props={props}")
            return raw_event

        return EVENT_IDS[raw_event.id].build_from_json(x)

    raw_event = RawEvent.build(x)
    if not raw_event.id in EVENT_IDS:
        # Log unknown events with full hex dump for reverse-engineering
        hex_dump = ' '.join(f'{b:02x}' for b in x[:EVENT_LEN])
        logger.debug(f"UNKNOWN_EVENT | id={raw_event.id} | seqNum={raw_event.seqNum} | timestamp={raw_event.timestamp.isoformat()} | bytes={hex_dump}")
        return raw_event

    return EVENT_IDS[raw_event.id].build(x)

def Events(x):
    # Accepts either a raw binary event stream or an iterable of pump-logs JSON events.
    if isinstance(x, (bytes, bytearray)):
        return (Event(bytearray(e)) for e in batched(x, EVENT_LEN))
    return (Event(e) for e in x)

def decode_raw_events(raw):
    return base64.b64decode(raw)
