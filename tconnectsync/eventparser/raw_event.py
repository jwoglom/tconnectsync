import struct

from dataclasses import dataclass

EVENT_LEN = 26
UINT16 = '>H'
UINT32 = '>I'

@dataclass
class RawEvent:
    source: int
    id: int
    timestamp: int
    seqNum: int

    @staticmethod
    def build(raw):
        source_and_id, = struct.unpack_from(UINT16, raw[:EVENT_LEN], 0)
        timestamp, = struct.unpack_from(UINT32, raw[:EVENT_LEN], 2)
        seqNum, = struct.unpack_from(UINT32, raw[:EVENT_LEN], 6)

        return RawEvent(
            source = (source_and_id & 0xF000) >> 12,
            id = source_and_id & 0x0FFF,
            timestamp = timestamp,
            seqNum = seqNum
        )