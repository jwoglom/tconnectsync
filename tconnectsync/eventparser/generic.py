import struct
import base64

from dataclasses import dataclass

from .raw_event import RawEvent, EVENT_LEN
from .events import EVENT_IDS
from .utils import batched


Event = lambda x: EVENT_IDS[RawEvent.build(x).id].build(x)
Events = lambda x: (Event(bytearray(e)) for e in batched(x, EVENT_LEN))

def decode_raw_events(raw):
    return base64.b64decode(raw)