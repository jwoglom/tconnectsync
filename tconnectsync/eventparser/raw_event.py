import struct
import arrow

from ..secret import TIMEZONE_NAME

from dataclasses import dataclass

EVENT_LEN = 26
# Big endian
UINT16 = '>H'
UINT32 = '>I'
TANDEM_EPOCH = 1199145600


@dataclass
class BaseEvent:
    @staticmethod
    def build(raw):
        raise NotImplemented

    @property
    def eventTimestamp(self):
        raise NotImplemented

    @property
    def eventId(self):
        raise NotImplemented

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

    @staticmethod
    def build_from_json(event):
        # pump-logs JSON events carry pumpDateTime (naive local wall-clock,
        # no tz). Reproduce the byte path: store timestampRaw as seconds since
        # TANDEM_EPOCH parsed AS IF UTC, so the .timestamp property re-forces
        # the same wall-clock into TIMEZONE_NAME. source is unused; raw bytes
        # are absent on the JSON path.
        timestampRaw = arrow.get(event["pumpDateTime"]).int_timestamp - TANDEM_EPOCH
        return RawEvent(
            source = 0,
            id = event["eventCode"],
            timestampRaw = timestampRaw,
            seqNum = event["sequenceNumber"],
            raw = b''
        )

    @property
    def timestamp(self):
        # Event timestamps do not have TZ data attached to them when parsed,
        # but represent the user's time zone setting. So we keep the time
        # referenced on them, but force the timezone to what the user
        # requests via the TZ secret.
        return arrow.get(TANDEM_EPOCH + self.timestampRaw, tzinfo='UTC').replace(tzinfo=TIMEZONE_NAME)

    @property
    def eventId(self):
        return self.id

    @property
    def eventTimestamp(self):
        return self.timestamp

    def todict(self):
        return dict(
            id=self.id,
            name="RawEvent",
            seqNum=self.seqNum,
            eventTimestamp=self.eventTimestamp.isoformat(), # Puts the event timestamp in ISO format, hopefully stopping the mismatch with nightscout
            raw=''.join('{:02x}'.format(x) for x in self.raw),
        )
