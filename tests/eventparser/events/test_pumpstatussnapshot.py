#!/usr/bin/env python3

import unittest

from tconnectsync.eventparser.generic import Event
from tconnectsync.eventparser.json_events import PumpStatusSnapshot
from tconnectsync.eventparser.raw_event import RawEvent, TANDEM_EPOCH
from tconnectsync.domain.tandemsource.event_class import EventClass

import struct

# Event 9 as the pump-logs endpoint returns it for a t:slim X2 (software
# 7.8.1) when no eventCodes filter is sent. Tandem's schema does not describe
# it, so it exists only as JSON.
SNAPSHOT_9 = {
    "deviceAssignmentId": "e2e-device-assignment-id",
    "eventCode": 9,
    "sequenceGroup": 0,
    "sequenceNumber": 612345,
    "pumpDateTime": "2026-11-19T11:29:02",
    "eventProperties": {
        "insulin": 115, "insulinBars": 2, "iob": 1, "iobHours": 3, "iobMinutes": 51,
        "selectedIob": 1, "abc": 94, "ibc": 95, "batteryBars": 5,
        "controllerAbc": 255, "controllerIbc": 255, "controllerBattBar": 255, "reservedD14": 0,
    },
    "estimatedDateTime": "2026-11-19T10:32:47Z",
}


class TestPumpStatusSnapshot(unittest.TestCase):
    def test_json_event_9_is_parsed(self):
        ev = Event(SNAPSHOT_9)

        self.assertIsInstance(ev, PumpStatusSnapshot)
        self.assertEqual(ev.eventId, 9)
        self.assertEqual(ev.seqNum, 612345)
        self.assertEqual(ev.insulin, 115)
        self.assertEqual(ev.abc, 94)
        # the event's own tenths-of-a-unit iob stays reachable, unconverted
        self.assertEqual(ev.props["iob"], 1)
        # pumpDateTime is the pump's wall clock, like every other event
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DD HH:mm:ss'), '2026-11-19 11:29:02')
        self.assertEqual(ev.eventTimestamp, ev.raw.timestamp)

    def test_zero_is_kept(self):
        event = dict(SNAPSHOT_9, eventProperties=dict(SNAPSHOT_9["eventProperties"], insulin=0, abc=0))
        ev = Event(event)

        self.assertEqual(ev.insulin, 0)
        self.assertEqual(ev.abc, 0)

    def test_missing_properties_are_none(self):
        ev = Event(dict(SNAPSHOT_9, eventProperties={}))

        self.assertIsInstance(ev, PumpStatusSnapshot)
        self.assertIsNone(ev.insulin)
        self.assertIsNone(ev.abc)

    def test_todict(self):
        d = Event(SNAPSHOT_9).todict()

        self.assertEqual(d["id"], 9)
        self.assertEqual(d["name"], "PUMP_STATUS_SNAPSHOT")
        self.assertEqual(d["seqNum"], 612345)
        self.assertEqual(d["insulin"], 115)
        self.assertEqual(d["abc"], 94)

    def test_belongs_to_device_status(self):
        self.assertEqual(EventClass.for_event(Event(SNAPSHOT_9)), EventClass.DEVICE_STATUS)
        self.assertEqual(EventClass.for_event(PumpStatusSnapshot), EventClass.DEVICE_STATUS)

    def test_binary_event_9_stays_raw(self):
        # No byte layout is known for event 9, so the binary path does not
        # pretend to decode it.
        raw = bytearray(26)
        struct.pack_into('>H', raw, 0, 9)
        struct.pack_into('>I', raw, 2, 595942142)
        struct.pack_into('>I', raw, 6, 612345)

        ev = Event(raw)

        self.assertIs(type(ev), RawEvent)
        self.assertEqual(ev.id, 9)
        self.assertIsNone(EventClass.for_event(ev))


if __name__ == '__main__':
    unittest.main()
