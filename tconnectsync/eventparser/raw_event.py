import struct
import arrow

from dataclasses import dataclass

EVENT_LEN = 26
UINT16 = '>H'
UINT32 = '>I'
TANDEM_EPOCH = 1199145600

@dataclass
class RawEvent:
    source: int
    id: int
    timestampRaw: int
    seqNum: int
    raw: bytearray

    @staticmethod
    def build(raw):
        source_and_id, = struct.unpack_from(UINT16, raw[:EVENT_LEN], 0)
        timestampRaw, = struct.unpack_from(UINT32, raw[:EVENT_LEN], 2)
        seqNum, = struct.unpack_from(UINT32, raw[:EVENT_LEN], 6)

        return RawEvent(
            source = (source_and_id & 0xF000) >> 12,
            id = source_and_id & 0x0FFF,
            timestampRaw = timestampRaw,
            seqNum = seqNum,
            raw = raw
        )
    
    @property
    def timestamp(self):
        return arrow.get(TANDEM_EPOCH + self.timestampRaw)
