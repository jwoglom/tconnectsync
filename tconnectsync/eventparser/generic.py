import struct
import base64

from dataclasses import dataclass

from .raw_event import RawEvent, EVENT_LEN
from .events import EVENT_IDS
from .utils import batched


def Event(x):
    raw_event = RawEvent.build(x)
    if not raw_event.id in EVENT_IDS:
        return raw_event

    return EVENT_IDS[raw_event.id].build(x)

Events = lambda x: (Event(bytearray(e)) for e in batched(x, EVENT_LEN))

def decode_raw_events(raw):
    return base64.b64decode(raw)