import struct

from dataclasses import dataclass

from .raw_event import RawEvent, EVENT_LEN
from .codegen import EVENT_IDS
from .utils import batched


Event = lambda x: EVENT_IDS[RawEvent.build(x).id].build(x)
Events = lambda x: (Event(bytearray(e)) for e in batched(x, EVENT_LEN))